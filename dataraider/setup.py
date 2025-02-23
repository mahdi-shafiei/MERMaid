from setuptools import setup, find_packages

setup(
    name="dataraider",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "requests",
        "opencv-python",
        "numpy",
        "regex", 
        "pubchempy", 
        "huggingface_hub"
    ],
    entry_points={
        "console_scripts": [
            "dataraider=scripts.run_dataraider:main"
        ]
    },
)
