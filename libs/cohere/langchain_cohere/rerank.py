from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence, Union

import cohere
from langchain_core.callbacks.manager import Callbacks
from langchain_core.documents import BaseDocumentCompressor, Document
from pydantic import Extra, root_validator, model_validator
from langchain_core.utils import get_from_dict_or_env
from pydantic import ConfigDict
from typing_extensions import Self




class CohereRerank(BaseDocumentCompressor):
    """Document compressor that uses `Cohere Rerank API`."""

    client: Any = None
    """Cohere client to use for compressing documents."""
    top_n: Optional[int] = 3
    """Number of documents to return."""
    model: Optional[str] = None
    """Model to use for reranking. Mandatory to specify the model name."""
    cohere_api_key: Optional[str] = None
    """Cohere API key. Must be specified directly or via environment variable 
        COHERE_API_KEY."""
    user_agent: str = "langchain:partner"
    """Identifier for the application making the request."""

    model_config = ConfigDict(extra="forbid",arbitrary_types_allowed=True,)

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        """Validate that api key and python package exists in environment."""
        if not (self.client or None):
            cohere_api_key = get_from_dict_or_env(
                values, "cohere_api_key", "COHERE_API_KEY"
            )
            client_name = self.user_agent
            self.client = cohere.Client(cohere_api_key, client_name=client_name)
        return self

    @model_validator(mode="after")
    def validate_model_specified(self) -> Self:
        """Validate that model is specified."""
        model = (self.model or None)
        if not model:
            raise ValueError(
                "Did not find `model`! Please "
                " pass `model` as a named parameter."
                " Please check out"
                " https://docs.cohere.com/reference/rerank"
                " for available models."
            )

        return self

    def rerank(
        self,
        documents: Sequence[Union[str, Document, dict]],
        query: str,
        *,
        rank_fields: Optional[Sequence[str]] = None,
        model: Optional[str] = None,
        top_n: Optional[int] = -1,
        max_chunks_per_doc: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Returns an ordered list of documents ordered by their relevance to the provided query.

        Args:
            query: The query to use for reranking.
            documents: A sequence of documents to rerank.
            rank_fields: A sequence of keys to use for reranking.
            model: The model to use for re-ranking. Default to self.model.
            top_n : The number of results to return. If None returns all results.
                Defaults to self.top_n.
            max_chunks_per_doc : The maximum number of chunks derived from a document.
        """  # noqa: E501
        if len(documents) == 0:  # to avoid empty api call
            return []
        docs = [
            doc.page_content if isinstance(doc, Document) else doc for doc in documents
        ]
        model = model or self.model
        top_n = top_n if (top_n is None or top_n > 0) else self.top_n
        results = self.client.rerank(
            query=query,
            documents=docs,
            model=model,
            top_n=top_n,
            rank_fields=rank_fields,
            max_chunks_per_doc=max_chunks_per_doc,
        )
        result_dicts = []
        for res in results.results:
            result_dicts.append(
                {"index": res.index, "relevance_score": res.relevance_score}
            )
        return result_dicts

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Optional[Callbacks] = None,
    ) -> Sequence[Document]:
        """
        Compress documents using Cohere's rerank API.

        Args:
            documents: A sequence of documents to compress.
            query: The query to use for compressing the documents.
            callbacks: Callbacks to run during the compression process.

        Returns:
            A sequence of compressed documents.
        """
        compressed = []
        for res in self.rerank(documents, query):
            doc = documents[res["index"]]
            doc_copy = Document(doc.page_content, metadata=deepcopy(doc.metadata))
            doc_copy.metadata["relevance_score"] = res["relevance_score"]
            compressed.append(doc_copy)
        return compressed
