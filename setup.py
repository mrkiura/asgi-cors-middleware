import pathlib
from setuptools import setup

HERE = pathlib.Path(__file__).parent

README = (HERE / "README.md").read_text()

setup(
    name="asgi-cors-middleware",
    version="0.0.1",
    description="Whitelist urls on ASGI applications allowing for cross origin "
                "requests",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/mrkiura/asgi-cors-middleware",
    author="Alex Kiura",
    author_email="kiuraalex@gmail.com",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    packages=["asgi_cors_middleware"],
    include_package_data=True,
    install_requires=["starlette"]
)
