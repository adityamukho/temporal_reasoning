import hashlib
import io
import os
import subprocess
import sys
import tarfile
import zipfile

import pytest
from unittest.mock import patch, MagicMock

# import install.py as a module (main() is guarded by __name__ == "__main__")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import install


class TestGetPlatformAsset:
    def test_linux_x86_64(self):
        with patch("sys.platform", "linux"), patch("platform.machine", return_value="x86_64"):
            assert install._get_platform_asset() == "minigraf-x86_64-unknown-linux-gnu.tar.xz"

    def test_linux_amd64_alias(self):
        with patch("sys.platform", "linux"), patch("platform.machine", return_value="amd64"):
            assert install._get_platform_asset() == "minigraf-x86_64-unknown-linux-gnu.tar.xz"

    def test_linux_aarch64(self):
        with patch("sys.platform", "linux"), patch("platform.machine", return_value="aarch64"):
            assert install._get_platform_asset() == "minigraf-aarch64-unknown-linux-gnu.tar.xz"

    def test_macos_arm64(self):
        with patch("sys.platform", "darwin"), patch("platform.machine", return_value="arm64"):
            assert install._get_platform_asset() == "minigraf-aarch64-apple-darwin.tar.xz"

    def test_macos_x86_64(self):
        with patch("sys.platform", "darwin"), patch("platform.machine", return_value="x86_64"):
            assert install._get_platform_asset() == "minigraf-x86_64-apple-darwin.tar.xz"

    def test_windows(self):
        with patch("sys.platform", "win32"):
            assert install._get_platform_asset() == "minigraf-x86_64-pc-windows-msvc.zip"

    def test_unsupported_platform_returns_none(self):
        with patch("sys.platform", "freebsd14"), patch("platform.machine", return_value="x86_64"):
            assert install._get_platform_asset() is None

    def test_unsupported_linux_arch_returns_none(self):
        with patch("sys.platform", "linux"), patch("platform.machine", return_value="riscv64"):
            assert install._get_platform_asset() is None


class TestVerifyChecksum:
    def test_valid_checksum_passes(self, tmp_path):
        data = b"fake minigraf binary content"
        asset = tmp_path / "minigraf.tar.xz"
        asset.write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        sha256_file = tmp_path / "minigraf.tar.xz.sha256"
        sha256_file.write_text(f"{digest}  minigraf.tar.xz\n")
        # Should not raise
        install._verify_checksum(str(asset), str(sha256_file))

    def test_invalid_checksum_raises(self, tmp_path):
        data = b"fake minigraf binary content"
        asset = tmp_path / "minigraf.tar.xz"
        asset.write_bytes(data)
        sha256_file = tmp_path / "minigraf.tar.xz.sha256"
        sha256_file.write_text("deadbeef" * 8 + "  minigraf.tar.xz\n")
        with pytest.raises(ValueError, match="SHA256 mismatch"):
            install._verify_checksum(str(asset), str(sha256_file))
