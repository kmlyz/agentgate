"""State fingerprint generator capturing environmental Git and filesystem state to prevent TOCTOU race conditions."""

import hashlib
import os
import subprocess


class FingerprintSecurityGate:
    """Computes deterministic environmental state fingerprints for Git and directory contexts."""

    @classmethod
    def capture_fingerprint(cls, path: str = ".") -> str:
        """Capture deterministic 64-character SHA-256 fingerprint of current repository state.

        Combines HEAD revision and working tree porcelain status to detect any state drift.
        """
        resolved_path = os.path.abspath(path)

        # 1. Check if git repository is available
        try:
            head_proc = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=resolved_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=5.0,
            )
            status_proc = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=resolved_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=5.0,
            )
            if head_proc.returncode == 0:
                head_rev = head_proc.stdout.strip()
                status_out = status_proc.stdout.strip()
                composite = f"git:{head_rev}:{status_out}".encode()
                return hashlib.sha256(composite).hexdigest()
        except (subprocess.SubprocessError, OSError):
            pass

        # 2. Fallback: Hash directory path and directory mtime/size
        try:
            stat_info = os.stat(resolved_path)
            composite = f"path:{resolved_path}:{stat_info.st_mtime}:{stat_info.st_size}".encode()
            return hashlib.sha256(composite).hexdigest()
        except OSError:
            # 3. Last-resort fallback for in-memory or transient non-existent paths
            return hashlib.sha256(f"transient:{resolved_path}".encode()).hexdigest()


def capture_gate_security_fingerprint(path: str = ".") -> str:
    """Convenience helper to capture state fingerprint conforming to hierarchical naming."""
    return FingerprintSecurityGate.capture_fingerprint(path=path)
