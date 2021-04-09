"""SCPI module specific errors"""
from typing import Any


class CommandError(RuntimeError):
    """Error executing SCPI command"""

    def __init__(self, command: str, code: int, message: str) -> None:
        """initialize the error"""
        self.command = command
        self.code = code
        self.message = message
        super().__init__()

    def __str__(self) -> str:
        """format as string"""
        return f"'{self.command}' returned error {self.code:d}: {self.message}"
