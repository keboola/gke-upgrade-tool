import setuptools

setuptools.setup(
    name="gke_upgrade_tool",
    author="Michal Kozák",
    description="Prepares KBC Stacks env.yaml for GKE upgrade",
    packages=setuptools.find_packages(),
    entry_points={"console_scripts": ["gke-upgrade-tool = gke_upgrade_tool.main:main"]},
    install_requires=["colorama", "ruamel.yaml", "requests", "semver"],
    setuptools_git_versioning={
        "enabled": True,
    },
    setup_requires=["setuptools-git-versioning<2"],
)
