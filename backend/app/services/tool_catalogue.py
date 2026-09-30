"""Central Tool Catalogue registry and execution dispatcher for the Claude Agent.

Defines schemas, type signatures, and parameters for Claude function calling.
Enforces closed-set execution and parameter safety.
"""
from typing import Any, Callable, Dict, List, Optional
from backend.app.services.charts import generate_chart
from backend.app.services.correlation import run_correlation
from backend.app.services.outliers import detect_outliers
from backend.app.services.segmentation import segment_compare
from backend.app.services.sql_tool import query_sql
from backend.app.services.summary import write_summary
from backend.app.services.timeseries import trend_analysis

# Canonical Provider-Agnostic Tool Definitions
CANONICAL_TOOL_DEFINITIONS = [
    {
        "name": "run_correlation",
        "description": "Calculates pairwise correlation across numeric columns in the dataset and flags strong linear relationships (|r| >= threshold).",
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "The dataset identifier or sample filename."},
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of numeric columns to correlate. If omitted, correlates all numeric columns."
                },
                "threshold": {
                    "type": "number",
                    "default": 0.4,
                    "description": "Minimum absolute correlation threshold to flag as a notable relationship."
                },
                "rationale": {
                    "type": "string",
                    "description": "Specific analytical justification or hypothesis explaining why this tool is selected."
                }
            },
            "required": ["dataset_id", "rationale"]
        }
    },
    {
        "name": "detect_outliers",
        "description": "Performs statistical outlier detection on numeric features using IQR (Interquartile Range), Z-Score, or Isolation Forest.",
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "The dataset identifier or sample filename."},
                "method": {
                    "type": "string",
                    "enum": ["iqr", "zscore", "isolation_forest"],
                    "default": "iqr",
                    "description": "Statistical method for anomaly detection."
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional subset of numeric columns to evaluate."
                },
                "rationale": {
                    "type": "string",
                    "description": "Specific analytical justification or hypothesis explaining why this tool is selected."
                }
            },
            "required": ["dataset_id", "rationale"]
        }
    },
    {
        "name": "segment_compare",
        "description": "Groups dataset by a categorical column and compares either a numeric metric (mean, median, sum, ANOVA significance) OR a binary/categorical target rate (e.g. 'Attrition', 'Converted', 'Churn' with proportions, n_used per segment, overall rate and denominator, and Chi-square test). NOTE: segment_column must be a true categorical business grouping (e.g. 'Department', 'Category', 'Region'). DO NOT select unique IDs.",
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "The dataset identifier or sample filename."},
                "segment_column": {"type": "string", "description": "The categorical column to group by (e.g. 'Department', 'Category', 'Region', 'Channel'). Must NOT be an ID column."},
                "metric_column": {"type": "string", "description": "The numeric column to compare (e.g. 'Annual_Salary', 'Unit_Price') OR a binary/categorical target column to compare rates for (e.g. 'Attrition', 'Converted', 'Churn')."},
                "rationale": {
                    "type": "string",
                    "description": "Specific analytical justification or hypothesis explaining why this tool is selected."
                }
            },
            "required": ["dataset_id", "segment_column", "metric_column", "rationale"]
        }
    },
    {
        "name": "trend_analysis",
        "description": "Performs chronological time-series analysis over a date-indexed column to detect trend direction (upward/downward/stable), slope, percentage change, and peaks.",
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "The dataset identifier or sample filename."},
                "date_column": {"type": "string", "description": "The date or timestamp column name."},
                "value_column": {"type": "string", "description": "The numeric metric to track over time."},
                "rationale": {
                    "type": "string",
                    "description": "Specific analytical justification or hypothesis explaining why this tool is selected."
                }
            },
            "required": ["dataset_id", "date_column", "value_column", "rationale"]
        }
    },
    {
        "name": "generate_chart",
        "description": "Generates a declarative Plotly chart specification dictionary for visual rendering in the dashboard.",
        "parameters": {
            "type": "object",
            "properties": {
                "result_type": {
                    "type": "string",
                    "enum": ["correlation", "trend", "segment_compare", "outlier", "bar", "line", "scatter", "heatmap"],
                    "description": "Type of visualization appropriate for the result."
                },
                "data": {
                    "type": "object",
                    "description": "The structured data payload generated by a preceding analysis tool."
                },
                "title": {"type": "string", "description": "Optional human-readable chart title."},
                "rationale": {
                    "type": "string",
                    "description": "Specific analytical justification or hypothesis explaining why this chart is generated."
                }
            },
            "required": ["result_type", "data", "rationale"]
        }
    },
    {
        "name": "query_sql",
        "description": "Executes a safe, read-only SQL query over the dataset via DuckDB. Two tables are exposed: 'data_clean' (all cleaned rows with sentinels and domain-invalid values converted to NULL and imputed) and 'data_observed' (only non-imputed observed values, with imputed cells set to NULL). 'df' and 'dataset' are aliases for data_clean.",
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "The dataset identifier or sample filename."},
                "sql": {"type": "string", "description": "Read-only SELECT query over table 'data_clean' or 'data_observed' (e.g., 'SELECT Category, SUM(Quantity) FROM data_clean GROUP BY 1')."},
                "rationale": {
                    "type": "string",
                    "description": "Specific analytical justification or hypothesis explaining why this query is executed."
                }
            },
            "required": ["dataset_id", "sql", "rationale"]
        }
    }
]

def get_canonical_tools() -> List[Dict[str, Any]]:
    """Return canonical tool specifications."""
    return list(CANONICAL_TOOL_DEFINITIONS)

def get_tools_for_claude() -> List[Dict[str, Any]]:
    """Convert canonical tool catalogue into Claude/Anthropic tool-schema format."""
    return [
        {
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool["parameters"]
        }
        for tool in CANONICAL_TOOL_DEFINITIONS
    ]

def get_tools_for_gemini() -> List[Any]:
    """Convert canonical tool catalogue into Google GenAI Tool format."""
    from google.genai import types
    declarations = [
        types.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters=tool["parameters"]
        )
        for tool in CANONICAL_TOOL_DEFINITIONS
    ]
    return [types.Tool(function_declarations=declarations)]

# Backwards compatibility alias
CLAUDE_TOOL_DEFINITIONS = get_tools_for_claude()

# Dispatcher mapping tool name to callable Python function
TOOL_REGISTRY: Dict[str, Callable] = {
    "run_correlation": run_correlation,
    "detect_outliers": detect_outliers,
    "segment_compare": segment_compare,
    "trend_analysis": trend_analysis,
    "generate_chart": generate_chart,
    "query_sql": query_sql,
    "write_summary": write_summary
}

def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Safely execute a tool from the closed catalogue with validation."""
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool '{tool_name}'. Available tools: {list(TOOL_REGISTRY.keys())}")
        
    func = TOOL_REGISTRY[tool_name]
    # Filter out 'rationale' or other meta-keys before passing to internal function
    exec_args = {k: v for k, v in arguments.items() if k != "rationale"}
    try:
        return func(**exec_args)
    except Exception as e:
        return {
            "status": "error",
            "tool": tool_name,
            "error_type": type(e).__name__,
            "message": str(e)
        }
