from collections import OrderedDict

import torch as T
import torch.nn as nn

from .. import utils

__all__ = ['Net', 'wrapper', 'Sequential', 'Lambda', 'Module', 'MultiSingleInputModule', 'MultiMultiInputModule',
           'SingleMultiInputModule']


class Net:
    """
    This abstract class is useful when you want to use
    :meth:`~neuralnet_pytorch.monitor.Monitor.run_training`.
    For a start, subclass this as the first parent.
    Then specify your optimization and schedule methods using :attr:`~optim`.
    You can specify your training procedure in :attr:`~train_procedure` and
    use :meth:`~learn` to perform optimization.
    If :meth:`~eval_procedure` is specified,
    Use :attr:`~stats` to collect your interested statistics from your training
    and evaluation.
    These statistics can be printed out or displayed in Tensorboard via
    :class:`~neuralnet_pytorch.monitor.Monitor`.

    Parameters
    ----------
    args
        arguments to be passed to `super`.
    kwargs
        keyword arguments to be passed to `super`.

    Attributes
    ----------
    optim
        a dictionary that contains the optimizer and scheduler for optimization.
    stats
        a dictionary to hold the interested statistics from training and evaluation.
        For each ``'train'`` and ``'eval'`` keys, an other dictionary with several
        built-in keys.
        The possible keys are: ``'scalars'``, ``'images'``, ``'histograms'``,
        and  ``'pointclouds'``.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.stats = {'train': {
                'scalars': {},
                'images': {},
                'histograms': {},
                'pointclouds': {}
            },
            'eval': {
                'scalars': {},
                'images': {},
                'histograms': {},
                'pointclouds': {}
            }
        }

    def train_procedure(self, *args, **kwargs):
        """
        Your training instructions can be specified here.
        This can return the loss to be optimized in :meth:`~learn`.
        You can use :attr:`~stats` to record the interested statistics.
        """

        raise NotImplementedError

    def learn(self, optim, *args, **kwargs):
        """
        The optimization can be defined here.
        Usually, it includes zeroing gradients, optimizing the loss,
        and collect statistics.
        """

        raise NotImplementedError

    def eval_procedure(self, *args, **kwargs):
        """
        If specified, an evaluation will be performed for your model.
        Use :attr:`~stats` to collect statistics.
        """

        raise NotImplementedError


class _LayerMethod:
    """
    This mixin class contains various attributes to extend :mod:`torch` modules.
    """

    @property
    @utils.validate
    def output_shape(self):
        """
        Returns the output shape of the module.
        """

        raise NotImplementedError

    @property
    def params(self):
        """
        Return a tuple of all the parameters in the module.
        """

        assert not hasattr(super(), 'params')
        return tuple(self.state_dict().values())

    @property
    def trainable(self):
        """
        Return a tuple of all parameters with :attr:`requires_grad` set to `True`.
        """

        assert not hasattr(super(), 'trainable')
        params = []
        if hasattr(self, 'parameters'):
            params = [p for p in self.parameters() if p.requires_grad]
        return tuple(params)

    @property
    def regularizable(self):
        """
        Returns a tuple of parameters to be regularized.
        """

        assert not hasattr(super(), 'regularizable')
        params = []
        if hasattr(self, 'weight'):
            if self.weight.requires_grad:
                params += [self.weight]

        for m in list(self.children()):
            if hasattr(m, 'regularizable'):
                params.extend(m.regularizable)

        return tuple(params)

    def save(self, param_file):
        """
        Save the weights of the model in :class:`numpy.nrdarray` format.

        :param param_file:
            path to the weight file.
        """

        assert not hasattr(super(), 'save')
        params_np = utils.bulk_to_numpy(self.params)
        params_dict = OrderedDict(zip(list(self.state_dict().keys()), params_np))
        T.save(params_dict, param_file)
        print('Model weights dumped to %s' % param_file)

    def load(self, param_file, eval=True):
        """
        Load the `numpy.ndarray` weights from file.

        :param param_file:
            path to the weight file.
        :param eval:
            whether to use evaluation mode or not.
        """

        assert not hasattr(super(), 'load')
        params_dict = T.load(param_file)
        self.load_state_dict(params_dict)
        if eval:
            self.eval()
        print('Model weights loaded from %s' % param_file)

    def reset_parameters(self):
        """
        This overloads the :meth:`torch.Module.reset_parameters` of the module.
        Used for custom weight initialization.
        """

        assert not hasattr(super(), 'reset_parameters')
        pass


@utils.add_simple_repr
class Module(nn.Module, _LayerMethod):
    """
    Similar to :class:`torch.nn.Module`, but extended by
    :class:`~neuralnet_pytorch.layers.layers._LayerMethod`.
    All the usages in native Pytorch are preserved.

    Parameters
    ----------
    input_shape
        shape of the tensor to be input to the modules.
        Can be a list, tuple, nested list/tuple or an integer.
    """

    def __init__(self, input_shape=None):
        super().__init__()
        self.input_shape = input_shape


@utils.add_simple_repr
class MultiSingleInputModule(Module):
    """
    This is an abstract class.
    This class computes the results of multiple modules given an input tensor,
    then fuses the results.

    Parameters
    ----------
    modules_or_tensors
        a list of modules or tensors whose results are fused together.

    Attributes
    ----------
    input_shape
        a list of input shapes of the incoming modules and tensors.
    """

    def __init__(self, *modules_or_tensors):
        assert all(isinstance(item, (nn.Module, T.Tensor)) for item in modules_or_tensors), \
            'All items in modules_or_tensors should be Pytorch modules or tensors'

        super().__init__()
        self.input_shape = []

        def foo(item):
            idx = len(list(self.children()))
            if isinstance(item, nn.Module):
                self.add_module('module%d' % idx, item)
                self.input_shape.append(item.output_shape)
            else:
                self.add_module('tensor%d' % idx, Lambda(lambda *args, **kwargs: item, input_shape=item.shape,
                                                         output_shape=item.shape))
                self.input_shape.append(item.shape)

        list(map(foo, modules_or_tensors))
        self.input_shape = tuple(self.input_shape)

    def forward(self, input, *args, **kwargs):
        outputs = [module(input, *args, **kwargs) for name, module in self.named_children()]
        return tuple(outputs)

    @property
    def trainable(self):
        return tuple()

    @property
    def params(self):
        return tuple()

    @property
    def regularizable(self):
        return tuple()


class MultiMultiInputModule(MultiSingleInputModule):
    """
    Similar to :class:`MultiSingleInputModule`, but each module has its own input tensor.
    """

    def __init__(self, *modules_or_tensors):
        super().__init__(*modules_or_tensors)

    def forward(self, *input, **kwargs):
        input_it = iter(input)
        outputs = [module(next(input_it), **kwargs) if name.startswith('module') else module()
                   for name, module in self.named_children()]
        return tuple(outputs)


class SingleMultiInputModule(Module):
    def __init__(self, module):
        super().__init__(module.output_shape)
        self.module = module

    @property
    @utils.validate
    def output_shape(self):
        return self.module.output_shape

    def forward(self, *input, **kwargs):
        return tuple([self.module(inp, **kwargs) for inp in input])

    @property
    def trainable(self):
        return tuple()

    @property
    def params(self):
        return tuple()

    @property
    def regularizable(self):
        return tuple()


@utils.add_simple_repr
class Sequential(nn.Sequential, _LayerMethod):
    """
    Similar to :class:`torch.nn.Sequential`, but extended by
    :class:`~neuralnet_pytorch.layers.layers._LayerMethod`.
    All the usages in native Pytorch are preserved.

    Parameters
    ----------
    args
        a list of modules as in :class:`torch.nn.Sequential`.
    input_shape
        shape of the input tensor. If ``None``, the functionality is
        the same as :class:`torch.nn.Sequential`.
    """

    def __init__(self, *args, input_shape=None):
        super().__init__(*args)
        self.input_shape = input_shape

    def __getitem__(self, idx):
        if isinstance(idx, slice):
            start = idx.start if idx.start else 0
            modules = list(self._modules.items())
            return Sequential(OrderedDict(modules[idx]), input_shape=modules[start][1].input_shape)
        else:
            return self._get_item_by_idx(self._modules.values(), idx)

    def forward(self, input, *args, **kwargs):
        for module in self._modules.values():
            input = module(input, *args, **kwargs)
        return input

    @property
    @utils.validate
    def output_shape(self):
        if self.input_shape is None:
            return None

        layers = list(self.children())
        return layers[-1].output_shape if layers else self.input_shape

    def reset_parameters(self):
        for m in self.children():
            m.reset_parameters()


def wrapper(input_shape=None, output_shape=None, *args, **kwargs):
    """
    A class decorator to wrap any :mod:`torch` module.

    :param input_shape:
        shape of the input to the module.
        Can be ``None``.
    :param output_shape:
        shape of the output tensor.
        If ``None``, the output shape is calculated by performing a forward pass.
    :param args:
        extra arguments needed by the module.
    :param kwargs:
        extra keyword arguments needed by the module.
    :return:
        The input module extended by :class:`~neuralnet_pytorch.layers.layers._LayerMethod`.

    Examples
    --------
    You can use this function directly on any :mod:`torch` module

    >>> import torch.nn as nn
    >>> import neuralnet_pytorch as nnt
    >>> dropout = nnt.wrapper(p=.2)(nn.Dropout2d)() # because wrapper returns a class!

    Alternatively, you can use it as a decorator

    .. code-block:: python

        import torch.nn as nn
        import neuralnet_pytorch as nnt

        @nnt.wrapper(# optional arguments for input and output shapes)
        class Foo(nn.Module):
            ...

        foo = Foo()
    """
    assert input_shape is None or isinstance(input_shape, (int, list, tuple)), 'Unknown type of input_shape'
    if isinstance(input_shape, int):
        input_shape = (input_shape,)

    def decorator(module: nn.Module):
        assert issubclass(module, nn.Module), 'module must be a subclass of Pytorch\'s Module'

        @utils.add_simple_repr
        class _Wrapper(module, _LayerMethod):
            def __init__(self):
                self.input_shape = input_shape
                self.output_shape_tmp = output_shape
                super().__init__(*args, **kwargs)

            def forward(self, input, *args, **kwargs):
                return super().forward(input, *args, **kwargs)

            @property
            @utils.validate
            def output_shape(self):
                if self.input_shape is None and self.output_shape_tmp is None:
                    return None

                if self.output_shape_tmp is not None:
                    return self.output_shape_tmp
                else:
                    none_indices = [k for k in range(len(self.input_shape)) if self.input_shape[k] is None]
                    shape = [1 if s is None else s for s in self.input_shape]
                    dummy = T.zeros(*shape)
                    try:
                        dummy = dummy.to(next(self.parameters()).device)
                    except StopIteration:
                        pass

                    dummy = self(dummy)
                    output_shape = list(dummy.shape)
                    for k in none_indices:
                        output_shape[k] = None
                    return tuple(output_shape)

        _Wrapper.__name__ = module.__name__
        _Wrapper.__doc__ = module.__doc__
        _Wrapper.__module__ = module.__module__
        return _Wrapper
    return decorator


class Lambda(Module):
    """
    Wraps a function as a :class:`~neuralnet_pytorch.layers.Module`.

    Parameters
    ----------
    func
        a callable function.
    input_shape
        shape of the input tensor.
    output_shape
        shape of the output tensor.
        If ``None``, the output shape is calculated by performing a forward pass.
    kwargs
        keyword arguments required by `func`.

    Examples
    --------
    You can easily wrap a :mod:`torch` function

    .. code-block:: python

        import torch as T
        import neuralnet_pytorch as nnt

        a, b = T.rand(3, 1), T.rand(3, 2)
        cat = nnt.Lambda(T.cat, dim=1)
        c = cat((a, b))
        print(c.shape)

    Also, it works for any self-defined function as well

    .. code-block:: python

        import neuralnet_pytorch as nnt

        def foo(x, y):
            return x + y

        a = T.rand(3, 3)
        print(a)
        foo_sum = nnt.Lambda(foo, y=1.)
        res = foo_sum(a)
        print(res)
    """

    def __init__(self, func, input_shape=None, output_shape=None, **kwargs):
        assert callable(func), 'The provided function must be callable'

        super().__init__(input_shape)
        self.output_shape_tmp = output_shape
        self.func = func
        self.kwargs = kwargs

    def forward(self, *input):
        return self.func(*input, **self.kwargs)

    @property
    @utils.validate
    def output_shape(self):
        if self.input_shape is None and self.output_shape_tmp is None:
            return None

        if self.output_shape_tmp is not None:
            return self.output_shape_tmp
        else:
            none_indices = [k for k in range(len(self.input_shape)) if self.input_shape[k] is None]
            shape = [1 if s is None else s for s in self.input_shape]
            dummy = T.zeros(*shape)
            try:
                dummy = dummy.to(next(self.parameters()).device)
            except StopIteration:
                pass

            dummy = self.forward(dummy)
            output_shape = list(dummy.shape)
            for k in none_indices:
                output_shape[k] = None
            return tuple(output_shape)

    def extra_repr(self):
        s = '{}'.format(self.func.__name__)
        return s
