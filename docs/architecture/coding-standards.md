# **10.0 Coding Standards**

* **Python Version**: **3.13+** is required.  
* **Type Checking**: **100% type annotation coverage** is mandatory, enforced by mypy with from \_\_future\_\_ import annotations enabled.  
* **Entity Specification**: **Pydantic v2** is the sole standard for data entities; @dataclass is forbidden.  
* **Async Programming**: All I/O operations **must** use the async/await syntax.  
* **Commit Messages**: **Conventional Commits** specification is mandatory for all Git commits.  
* **Contract-First**: All core data models **must** be imported from the packages/shared-contracts package.
