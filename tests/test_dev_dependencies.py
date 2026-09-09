"""Development dependency manifest smoke checks / 开发依赖清单冒烟检查。"""
import unittest


class DevelopmentDependencyTests(unittest.TestCase):
    def test_required_development_dependencies_import(self):
        import dns.resolver  # noqa: F401
        import httpx  # noqa: F401
        import playwright.sync_api  # noqa: F401
        import pytest  # noqa: F401
        import tzdata  # noqa: F401


if __name__ == "__main__":
    unittest.main()
