"""
Cross-domain Anti-Corruption Layer.

This layer protects our domain from external systems and other bounded contexts.
It translates between different models and protocols, ensuring our domain
remains pure and uncontaminated by external concerns.

Key responsibilities:
- Translate external gateway protocols (CTP, IB, etc.) to domain models
- Convert between different data formats (FIX, Binary, JSON)
- Handle protocol-specific details and quirks
- Protect domain from external API changes
"""
