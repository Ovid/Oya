"""Graph-aware architecture page generator."""

from __future__ import annotations

import networkx as nx

from oya.generation.overview import GeneratedPage
from oya.generation.prompts import SYSTEM_PROMPT, get_graph_architecture_prompt
from oya.graph.analysis import (
    filter_test_nodes,
    get_component_graph,
    select_top_entry_points,
    component_graph_to_mermaid,
)
from oya.graph.query import get_neighborhood


class GraphArchitectureGenerator:
    """Generates architecture page using the code graph.

    Uses graph analysis to produce deterministic diagrams,
    with LLM writing narrative to explain them.
    """

    def __init__(self, llm_client):
        """Initialize the generator.

        Args:
            llm_client: LLM client for narrative generation.
        """
        self.llm_client = llm_client

    async def generate(
        self,
        repo_name: str,
        graph: nx.DiGraph,
        component_summaries: dict[str, str] | None = None,
        min_confidence: float = 0.7,
        max_entry_points: int = 5,
        flow_hops: int = 2,
    ) -> GeneratedPage:
        """Generate architecture page from code graph.

        Args:
            repo_name: Name of the repository.
            graph: The code graph from Phase 2.
            component_summaries: Optional dict of component -> summary.
            min_confidence: Minimum confidence for diagram edges.
            max_entry_points: Maximum flow diagrams to generate.
            flow_hops: Hops for flow diagram neighborhood.

        Returns:
            GeneratedPage with architecture content.
        """
        # Filter out test code
        filtered_graph = filter_test_nodes(graph)

        # Build component diagram
        component_graph = get_component_graph(filtered_graph, min_confidence=min_confidence)
        component_diagram = component_graph_to_mermaid(component_graph)

        # Select top entry points and build flow diagrams
        entry_point_ids = select_top_entry_points(filtered_graph, n=max_entry_points)
        entry_points = []
        flow_diagrams = []

        for ep_id in entry_point_ids:
            node_data = filtered_graph.nodes.get(ep_id, {})
            fanout = filtered_graph.out_degree(ep_id)

            entry_points.append(
                {
                    "id": ep_id,
                    "name": node_data.get("name", ep_id.split("::")[-1]),
                    "file": node_data.get("file_path", ""),
                    "fanout": fanout,
                }
            )

            # Generate flow diagram
            neighborhood = get_neighborhood(
                filtered_graph, ep_id, hops=flow_hops, min_confidence=min_confidence
            )
            if neighborhood.nodes:
                flow_diagrams.append(
                    {
                        "entry_point": node_data.get("name", ep_id.split("::")[-1]),
                        "diagram": neighborhood.to_mermaid(),
                    }
                )

        # Build prompt and generate narrative
        prompt = get_graph_architecture_prompt(
            repo_name=repo_name,
            component_diagram=component_diagram,
            entry_points=entry_points,
            flow_diagrams=flow_diagrams,
            component_summaries=component_summaries or {},
        )

        content = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        # Append diagrams section
        content = self._append_diagrams(content, component_diagram, flow_diagrams)

        return GeneratedPage(
            content=content,
            page_type="architecture",
            path="architecture.md",
            word_count=len(content.split()),
        )

    def _append_diagrams(
        self,
        content: str,
        component_diagram: str,
        flow_diagrams: list[dict],
    ) -> str:
        """Append graph-derived diagrams to content."""
        lines = [content.rstrip(), "", "## Generated Diagrams", ""]

        lines.append("### Component Dependencies")
        lines.append("")
        lines.append("```mermaid")
        lines.append(component_diagram)
        lines.append("```")
        lines.append("")

        for flow in flow_diagrams:
            lines.append(f"### {flow['entry_point']} Flow")
            lines.append("")
            lines.append("```mermaid")
            lines.append(flow["diagram"])
            lines.append("```")
            lines.append("")

        return "\n".join(lines)
