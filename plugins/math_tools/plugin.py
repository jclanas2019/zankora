"""Mathematical calculations plugin."""
from __future__ import annotations

import math
from typing import Any

from gateway.domain.models import ToolPermission, ToolSpec
from gateway.plugins.registry import PluginRegistry


def calculate(expression: str) -> dict[str, Any]:
    """
    Evaluate a mathematical expression safely.
    
    Args:
        expression: Mathematical expression to evaluate
        
    Returns:
        Result of the calculation
    """
    # Safe evaluation context
    safe_dict = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
    }
    
    try:
        result = eval(expression, {"__builtins__": {}}, safe_dict)
        return {
            "expression": expression,
            "result": result,
            "success": True,
        }
    except Exception as e:
        return {
            "expression": expression,
            "error": str(e),
            "success": False,
        }


def statistics(numbers: list[float]) -> dict[str, float]:
    """
    Calculate statistics for a list of numbers.
    
    Args:
        numbers: List of numbers
        
    Returns:
        Statistical metrics
    """
    if not numbers:
        return {"error": "Empty list provided"}
    
    sorted_nums = sorted(numbers)
    n = len(numbers)
    
    return {
        "count": n,
        "sum": sum(numbers),
        "mean": sum(numbers) / n,
        "median": sorted_nums[n // 2] if n % 2 == 1 else (sorted_nums[n // 2 - 1] + sorted_nums[n // 2]) / 2,
        "min": min(numbers),
        "max": max(numbers),
        "range": max(numbers) - min(numbers),
    }


def fibonacci(n: int) -> dict[str, Any]:
    """
    Calculate Fibonacci sequence up to n terms.
    
    Args:
        n: Number of terms
        
    Returns:
        Fibonacci sequence
    """
    if n <= 0:
        return {"error": "n must be positive"}
    if n > 100:
        return {"error": "n too large (max 100)"}
    
    sequence = []
    a, b = 0, 1
    
    for _ in range(n):
        sequence.append(a)
        a, b = b, a + b
    
    return {
        "n": n,
        "sequence": sequence,
        "last_term": sequence[-1] if sequence else 0,
    }


def prime_factors(n: int) -> dict[str, Any]:
    """
    Find prime factors of a number.
    
    Args:
        n: Number to factorize
        
    Returns:
        Prime factors
    """
    if n <= 1:
        return {"error": "Number must be greater than 1"}
    
    factors = []
    d = 2
    
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    
    if n > 1:
        factors.append(n)
    
    return {
        "number": n * math.prod(factors),  # Original number
        "factors": factors,
        "unique_factors": list(set(factors)),
    }


def register(registry: PluginRegistry) -> None:
    """Register math plugin tools."""
    
    registry.register_tool(
        ToolSpec(
            name="math.calculate",
            description="Evaluate mathematical expressions safely (supports basic operations and common math functions)",
            permission=ToolPermission.read,
            func=calculate,
            parameters={
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate (e.g., 'sqrt(16) + 2 * 3')",
                }
            },
        )
    )
    
    registry.register_tool(
        ToolSpec(
            name="math.statistics",
            description="Calculate statistical metrics (mean, median, min, max, etc.) for a list of numbers",
            permission=ToolPermission.read,
            func=statistics,
            parameters={
                "numbers": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "List of numbers to analyze",
                }
            },
        )
    )
    
    registry.register_tool(
        ToolSpec(
            name="math.fibonacci",
            description="Generate Fibonacci sequence up to n terms",
            permission=ToolPermission.read,
            func=fibonacci,
            parameters={
                "n": {
                    "type": "integer",
                    "description": "Number of Fibonacci terms to generate (max 100)",
                }
            },
        )
    )
    
    registry.register_tool(
        ToolSpec(
            name="math.prime_factors",
            description="Find prime factorization of a number",
            permission=ToolPermission.read,
            func=prime_factors,
            parameters={
                "n": {
                    "type": "integer",
                    "description": "Number to factorize (must be > 1)",
                }
            },
        )
    )
    
    print("✅ Math plugin loaded successfully")
