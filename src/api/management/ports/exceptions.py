"""Domain exceptions for Management bounded context.

These exceptions represent domain-level errors that occur during
repository and service operations. They are caught and translated by
the application layer into HTTP responses.
"""


class UnauthorizedError(Exception):
    """Raised when a user lacks the required permission to perform an operation.

    The application layer (FastAPI routes) should catch this and return 403.
    """

    pass


class DuplicateKnowledgeGraphNameError(Exception):
    """Raised when a knowledge graph with the same name already exists in the workspace.

    Business rule: KnowledgeGraph names must be unique within a workspace.
    """

    pass


class DuplicateDataSourceNameError(Exception):
    """Raised when a data source with the same name already exists in the knowledge graph.

    Business rule: DataSource names must be unique within a knowledge graph.
    """

    pass


class KnowledgeGraphNotFoundError(Exception):
    """Raised when a requested KnowledgeGraph does not exist.

    The application layer should catch this and return 404.
    """

    pass


class DataSourceNotFoundError(Exception):
    """Raised when a requested DataSource does not exist.

    The application layer should catch this and return 404.
    """

    pass
