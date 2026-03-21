from setuptools import setup


setup(
    name="treasure-furnace",
    version="0.1.0",
    description="Standalone import, preview, install, and validation toolchain for HoluBot Treasures.",
    py_modules=["treasure_forge", "pocket_manifest_builder"],
    packages=["adapters", "core"],
    install_requires=[
        "httpx>=0.27,<1",
        "PyYAML>=6,<7",
    ],
    extras_require={
        "dev": ["pytest>=8,<9"],
        "test": ["pytest>=8,<9"],
    },
    entry_points={
        "console_scripts": [
            "treasure-furnace=treasure_forge:main",
        ]
    },
)
