from setuptools import setup

setup(
    name="sample-app",
    install_requires=[
        "click==8.1.7",
    ],
    extras_require={
        "dev": ["pytest>=8.0"],
    },
)
