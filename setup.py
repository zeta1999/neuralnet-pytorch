import sys
from setuptools import setup, find_packages
import os
import versioneer

version_data = versioneer.get_versions()
CMD_CLASS = versioneer.get_cmdclass()

if version_data['error'] is not None:
    # Get the fallback version
    # We can't import neuralnet_pytorch.version as it isn't yet installed, so parse it.
    fname = os.path.join(os.path.split(__file__)[0], "neuralnet_pytorch", "version.py")
    with open(fname, "r") as f:
        lines = f.readlines()
    lines = [l for l in lines if l.startswith("FALLBACK_VERSION")]
    assert len(lines) == 1

    FALLBACK_VERSION = lines[0].split("=")[1].strip().strip('""')

    version_data['version'] = FALLBACK_VERSION


def get_extensions():
    if '--cuda-ext' in sys.argv:
        import glob
        from torch.utils.cpp_extension import BuildExtension, CUDAExtension
        CMD_CLASS.update({'build_ext': BuildExtension})
        ext_root = 'neuralnet_pytorch/extensions'
        ext_src = glob.glob(os.path.join(ext_root, 'csrc/*.cpp')) + glob.glob(os.path.join(ext_root, 'csrc/*.cu'))
        ext_include = os.path.join(ext_root, 'include')
        sys.argv.remove("--cuda-ext")
        return [
            CUDAExtension(
            name='neuralnet_pytorch.ext',
            sources=ext_src,
            include_dirs=[ext_include]
        )]
    else:
        return []


def setup_package():
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()

    cuda_ext = get_extensions()
    setup(
        name='neuralnet-pytorch',
        version=version_data['version'],
        description='A high-level library on top of Pytorch.',
        long_description=long_description,
        long_description_content_type='text/markdown',
        url='https://github.com/justanhduc/neuralnet-pytorch',
        author='Duc Nguyen',
        author_email='adnguyen@yonsei.ac.kr',
        classifiers=[
            'Development Status :: 3 - Alpha',
            'Intended Audience :: End Users/Desktop',
            'License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)',
            'Operating System :: Microsoft :: Windows :: Windows 10',
            'Operating System :: POSIX :: Linux',
            'Programming Language :: Python :: 3 :: Only',
            'Programming Language :: Python :: 3.5',
            'Programming Language :: Python :: 3.6',
            'Programming Language :: Python :: 3.7'
        ],
        platforms=['Windows', 'Linux'],
        packages=find_packages(exclude=['docs', 'tests', 'examples']),
        ext_modules=cuda_ext,
        cmdclass=CMD_CLASS,
        install_requires=['matplotlib', 'scipy', 'numpy', 'tb-nightly', 'imageio', 'future', 'tensorboardX'],
        extras_require={
            'gin': ['gin-config'],
            'geom': ['pykeops', 'geomloss'],
            'visdom': ['visdom'],
            'slack': ['slackclient']
        },
        project_urls={
            'Bug Reports': 'https://github.com/justanhduc/neuralnet-pytorch/issues',
            'Source': 'https://github.com/justanhduc/neuralnet-pytorch',
        },
    )


if __name__ == '__main__':
    setup_package()
