# **13.0 Code Evolution Guidelines**

* **Core Principle**: A single source of truth for all features; file versioning (e.g., service\_v2.py, service\_optimized.py) is strictly forbidden. Code history must be managed by Git.
* **Evolution Patterns**: New functionality should be introduced via **Feature Flags** or the **Strategy Pattern**.
* **Migration Process**: Deprecation of old code must follow a three-step process: ensure backward compatibility, issue deprecation warnings, and remove the code in the next major version.
