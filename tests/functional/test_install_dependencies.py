import itertools
import textwrap
from pathlib import Path

import pytest

from tests.lib import (
    PipTestEnvironment,
    TestData,
    TestFailure,
    create_basic_wheel_for_package,
    create_really_basic_wheel,
)


@pytest.fixture
def reqs_test_package(tmp_path: Path) -> Path:
    project_path = tmp_path / "pkga"
    project_path.mkdir()
    project_path.joinpath("pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [build-system]
            requires = ["setuptools"]
            build-backend = "setuptools.build_meta"

            [project]
            name = "pkga"
            version = "1.0"
            dependencies = [
              "simple==3.0",
            ]
            [project.optional-dependencies]
            doc = ["simple2==2.0"]
            """
        )
    )
    return project_path


@pytest.fixture
def reqs_test_package_wheel(script: PipTestEnvironment) -> Path:
    return create_basic_wheel_for_package(
        script,
        "pkga",
        "1.0",
        depends=["simple==3.0"],
        extras={"doc": ["simple2==2.0"]},
    )


def test_install_only_deps(
    script: PipTestEnvironment, reqs_test_package: Path, shared_data: TestData
) -> None:
    """Test installing project dependencies."""
    result = script.pip(
        "install",
        "--disable-pip-version-check",
        "--no-index",
        "--find-links",
        str(shared_data.packages),
        "--only-deps",
        str(reqs_test_package),
    )
    result.assert_installed("simple", editable=False, editable_vcs=False)
    with pytest.raises(TestFailure):
        result.assert_installed("pkga", editable=False, editable_vcs=False)
    with pytest.raises(TestFailure):
        result.assert_installed("simple2", editable=False, editable_vcs=False)


def test_install_only_deps_and_optional_deps(
    script: PipTestEnvironment, reqs_test_package: Path, shared_data: TestData
) -> None:
    """Test installing project and optional dependencies."""
    result = script.pip(
        "install",
        "--disable-pip-version-check",
        "--no-index",
        "--find-links",
        str(shared_data.packages),
        "--only-deps",
        str(reqs_test_package) + "[doc]",
    )
    result.assert_installed("simple", editable=False, editable_vcs=False)
    result.assert_installed("simple2", editable=False, editable_vcs=False)
    with pytest.raises(TestFailure):
        result.assert_installed("pkga", editable=False, editable_vcs=False)


def test_install_only_deps_for_wheel(
    script: PipTestEnvironment, reqs_test_package_wheel: Path, shared_data: TestData
) -> None:
    """Test installing project dependencies."""
    result = script.pip(
        "--verbose",
        "install",
        "--disable-pip-version-check",
        "--no-index",
        "--find-links",
        str(shared_data.packages),
        "--only-deps",
        str(reqs_test_package_wheel),
    )
    result.assert_installed("simple", editable=False, editable_vcs=False)
    with pytest.raises(TestFailure):
        result.assert_installed("pkga", editable=False, editable_vcs=False)
    with pytest.raises(TestFailure):
        result.assert_installed("simple2", editable=False, editable_vcs=False)


@pytest.fixture
def reqs_test_package_with_dummy_buildsystem(
    tmp_path: Path, shared_data: TestData
) -> Path:
    for name in ["fakebuildsystem", "buildsystemdependency"]:
        shared_data.packages.joinpath(f"{name}-1.0-py2.py3-none-any.whl").write_bytes(
            create_really_basic_wheel(name, "1.0")
        )
    pkga_wheel_path = shared_data.root.joinpath("pkga-1.0-py2.py3-none-any.whl")
    pkga_wheel_path.write_bytes(create_really_basic_wheel("pkga", "1.0"))
    project_path = tmp_path / "pkga"
    project_path.mkdir()
    project_path.joinpath("pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [build-system]
            requires = ["fakebuildsystem==1.0"]
            build-backend = "buildbackend"
            backend-path = ["."]

            [project]
            name = "pkga"
            version = "1.0"
            """
        )
    )
    project_path.joinpath("buildbackend.py").write_text(
        textwrap.dedent(
            f"""\
            import os
            def prepare_metadata_for_build_wheel(metadata_directory, config_settings):
                dirname = 'pkga-1.0.dist-info'
                dirpath = os.path.join(metadata_directory, dirname)
                os.mkdir(dirpath)
                with open(os.path.join(dirpath, 'METADATA'), 'w') as f:
                    f.writelines([
                        'Metadata-Version: 1.0', os.linesep,
                        'Name: pkga', os.linesep,
                        'Version: 1.0', os.linesep,
                    ])
                return dirname
            def get_requires_for_build_wheel(config_settings):
                return ["buildsystemdependency==1.0"]
            def build_wheel(
                wheel_directory,
                config_settings=None,
                metadata_directory=None
            ):
                return "{pkga_wheel_path}"
            def build_sdist(sdist_directory, config_settings=None):
                return "pkga-1.0.tar.gz"
            """
        )
    )
    return project_path


def test_install_only_build_deps(
    script: PipTestEnvironment,
    reqs_test_package_with_dummy_buildsystem: Path,
    shared_data: TestData,
) -> None:
    """Test installing project dependencies."""
    result = script.pip(
        "--verbose",
        "install",
        "--disable-pip-version-check",
        "--no-index",
        "--find-links",
        str(shared_data.packages),
        "--only-build-deps",
        str(reqs_test_package_with_dummy_buildsystem),
    )
    assert "Successfully installed fakebuildsystem-1.0" in result.stderr
    with pytest.raises(TestFailure):
        result.assert_installed("simple", editable=False, editable_vcs=False)
    with pytest.raises(TestFailure):
        result.assert_installed("pkga", editable=False, editable_vcs=False)
    with pytest.raises(TestFailure):
        result.assert_installed("simple2", editable=False, editable_vcs=False)


@pytest.mark.parametrize(
    "option1,option2",
    itertools.combinations(["no", "only", "only-build"], r=2),
)
def test_install_dependency_options_are_mutually_exclusive(
    script: PipTestEnvironment,
    reqs_test_package: Path,
    option1: str,
    option2: str,
) -> None:
    """Test dependency options are mutually exclusive."""
    result = script.pip(
        "install",
        "--disable-pip-version-check",
        "--no-index",
        f"--{option1}-deps",
        f"--{option2}-deps",
        str(reqs_test_package),
        expect_error=True,
    )
    assert f"--{option1}-deps" in result.stderr
    assert f"--{option2}-deps" in result.stderr
