from __future__ import annotations

import secrets


class CodeGenerator:
    @staticmethod
    def generate(length: int) -> str:
        if length <= 0:
            raise ValueError("Code length must be positive")
        upper_bound = 10**length
        return f"{secrets.randbelow(upper_bound):0{length}d}"

    @staticmethod
    def is_valid(code: str, length: int) -> bool:
        return len(code) == length and code.isascii() and code.isdigit()

    @classmethod
    def patient_code(cls, length: int = 6) -> str:
        return cls.generate(length)

    @classmethod
    def assignment_code(cls, length: int = 8) -> str:
        return cls.generate(length)
