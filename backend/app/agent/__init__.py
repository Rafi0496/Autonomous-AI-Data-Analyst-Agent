"""Agent module containing orchestrator and claim verification."""

def __getattr__(name: str):
    if name == "PlanActReflectOrchestrator":
        from backend.app.agent.orchestrator import PlanActReflectOrchestrator
        return PlanActReflectOrchestrator
    if name == "validate_citations":
        from backend.app.agent.citation_checker import validate_citations
        return validate_citations
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["PlanActReflectOrchestrator", "validate_citations"]
