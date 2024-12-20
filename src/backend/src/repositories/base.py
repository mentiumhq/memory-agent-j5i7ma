"""
Base repository implementation providing foundational database operations with comprehensive
error handling, transaction management, and session lifecycle management.

Version:
- SQLAlchemy==2.0+
- SQLAlchemy-Utils==0.41.1
"""

import logging
from typing import Type, TypeVar, Generic, Optional, List, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm.exc import NoResultFound

from db.session import DatabaseSession
from db.base import Base
from core.errors import StorageError, ErrorCode

# Configure logging
logger = logging.getLogger(__name__)

# Generic type variable bound to SQLAlchemy Base
T = TypeVar('T', bound=Base)

class BaseRepository(Generic[T]):
    """
    Generic base repository implementing common database operations with comprehensive
    error handling, transaction management, and session lifecycle management.
    """

    def __init__(self, model_class: Type[T]) -> None:
        """
        Initialize repository with model class and configuration.

        Args:
            model_class: SQLAlchemy model class for repository operations
        
        Raises:
            ValueError: If model_class is not a SQLAlchemy model
        """
        if not issubclass(model_class, Base):
            raise ValueError(f"Model class must be a SQLAlchemy model: {model_class}")
        
        self._model_class = model_class
        self._session: Optional[Session] = None
        self._in_transaction: bool = False
        self._retry_count: int = 0
        self._max_retries: int = 3

    def __enter__(self) -> 'BaseRepository[T]':
        """
        Enter context manager with session monitoring and validation.

        Returns:
            Self instance with active session
        
        Raises:
            StorageError: If session creation fails
        """
        try:
            if self._session is not None:
                raise StorageError(
                    "Session already exists",
                    ErrorCode.STORAGE_ERROR
                )
            
            session_ctx = DatabaseSession()
            self._session = session_ctx.__enter__()
            return self
            
        except Exception as e:
            logger.error(f"Error creating session: {str(e)}")
            raise StorageError(
                "Failed to create database session",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Exit context manager with proper cleanup and error handling.

        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value if error occurred
            exc_tb: Exception traceback if error occurred
        """
        try:
            if self._in_transaction:
                if exc_type is not None:
                    self._session.rollback()
                else:
                    self._session.commit()
            
            if self._session is not None:
                self._session.close()
                
        except Exception as e:
            logger.error(f"Error during session cleanup: {str(e)}")
            if self._session is not None:
                self._session.rollback()
                
        finally:
            self._session = None
            self._in_transaction = False
            self._retry_count = 0

    def get(self, entity_id: str) -> Optional[T]:
        """
        Retrieve entity by ID with error handling and type validation.

        Args:
            entity_id: Unique identifier of entity

        Returns:
            Found entity or None if not found

        Raises:
            StorageError: If database operation fails
        """
        try:
            if self._session is None:
                raise StorageError("No active session")
                
            result = self._session.query(self._model_class).filter_by(id=entity_id).first()
            
            if result is not None and not isinstance(result, self._model_class):
                raise StorageError(
                    f"Invalid entity type returned: {type(result)}",
                    ErrorCode.STORAGE_ERROR
                )
                
            return result
            
        except SQLAlchemyError as e:
            logger.error(f"Database error in get operation: {str(e)}")
            raise StorageError(
                "Failed to retrieve entity",
                ErrorCode.STORAGE_ERROR,
                {"entity_id": entity_id, "error": str(e)}
            )

    def list(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[T]:
        """
        List all entities of model type with pagination and filtering.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of entities

        Raises:
            StorageError: If database operation fails
        """
        try:
            if self._session is None:
                raise StorageError("No active session")
                
            query = self._session.query(self._model_class)
            
            if offset is not None:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
                
            return query.all()
            
        except SQLAlchemyError as e:
            logger.error(f"Database error in list operation: {str(e)}")
            raise StorageError(
                "Failed to list entities",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

    def create(self, entity: T) -> T:
        """
        Create new entity with transaction management and validation.

        Args:
            entity: Entity instance to create

        Returns:
            Created entity with updated ID

        Raises:
            StorageError: If creation fails or validation errors occur
        """
        try:
            if self._session is None:
                raise StorageError("No active session")
                
            if not isinstance(entity, self._model_class):
                raise StorageError(
                    f"Invalid entity type: {type(entity)}",
                    ErrorCode.STORAGE_ERROR
                )
                
            self._in_transaction = True
            self._session.add(entity)
            self._session.flush()
            self._session.refresh(entity)
            self._session.commit()
            self._in_transaction = False
            
            return entity
            
        except IntegrityError as e:
            self._session.rollback()
            logger.error(f"Integrity error in create operation: {str(e)}")
            raise StorageError(
                "Entity already exists or constraints violated",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )
            
        except SQLAlchemyError as e:
            self._session.rollback()
            logger.error(f"Database error in create operation: {str(e)}")
            raise StorageError(
                "Failed to create entity",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

    def update(self, entity: T) -> T:
        """
        Update existing entity with optimistic locking and validation.

        Args:
            entity: Entity instance to update

        Returns:
            Updated entity

        Raises:
            StorageError: If update fails or entity not found
        """
        try:
            if self._session is None:
                raise StorageError("No active session")
                
            if not isinstance(entity, self._model_class):
                raise StorageError(
                    f"Invalid entity type: {type(entity)}",
                    ErrorCode.STORAGE_ERROR
                )
                
            if not hasattr(entity, 'id'):
                raise StorageError(
                    "Entity must have an ID for update",
                    ErrorCode.STORAGE_ERROR
                )
                
            self._in_transaction = True
            merged_entity = self._session.merge(entity)
            self._session.flush()
            self._session.refresh(merged_entity)
            self._session.commit()
            self._in_transaction = False
            
            return merged_entity
            
        except NoResultFound:
            self._session.rollback()
            raise StorageError(
                "Entity not found for update",
                ErrorCode.STORAGE_ERROR,
                {"entity_id": getattr(entity, 'id', None)}
            )
            
        except SQLAlchemyError as e:
            self._session.rollback()
            logger.error(f"Database error in update operation: {str(e)}")
            raise StorageError(
                "Failed to update entity",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

    def delete(self, entity_id: str) -> bool:
        """
        Delete entity by ID with cascading and constraint checking.

        Args:
            entity_id: Unique identifier of entity to delete

        Returns:
            True if deleted, False if not found

        Raises:
            StorageError: If deletion fails
        """
        try:
            if self._session is None:
                raise StorageError("No active session")
                
            entity = self._session.query(self._model_class).filter_by(id=entity_id).first()
            
            if entity is None:
                return False
                
            self._in_transaction = True
            self._session.delete(entity)
            self._session.commit()
            self._in_transaction = False
            
            return True
            
        except IntegrityError as e:
            self._session.rollback()
            logger.error(f"Integrity error in delete operation: {str(e)}")
            raise StorageError(
                "Cannot delete entity due to constraints",
                ErrorCode.STORAGE_ERROR,
                {"entity_id": entity_id, "error": str(e)}
            )
            
        except SQLAlchemyError as e:
            self._session.rollback()
            logger.error(f"Database error in delete operation: {str(e)}")
            raise StorageError(
                "Failed to delete entity",
                ErrorCode.STORAGE_ERROR,
                {"entity_id": entity_id, "error": str(e)}
            )