import setuptools

setuptools.setup(
    name="gke_upgrade_tool",
    version="0.0.1",
    author="Michal Kozák",
    description="Prepares KBC Stacks env.yaml for GKE upgrade",
    packages=setuptools.find_packages(),
    entry_points={"console_scripts": ["gke-upgrade-tool = gke_upgrade_tool.main:main"]},
    install_requires=["ruamel.yaml", "requests"],
)
