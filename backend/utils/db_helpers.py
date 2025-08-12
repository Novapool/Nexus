"""
Type-safe database query helpers for SQLAlchemy
"""

from typing import TypeVar, Optional, Type, List, Any, Dict
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.engine import Result
from sqlalchemy.sql import Select
import logging

logger = logging.getLogger(__name__)

# Generic type variable for database models
T = TypeVar('T')


async def get_by_id(
    db: AsyncSession, 
    model_class: Type[T], 
    id_value: str
) -> Optional[T]:
    """Type-safe database query helper to get a record by ID"""
    try:
        stmt: Select[tuple[T]] = select(model_class).where(model_class.id == id_value)
        result: Result[tuple[T]] = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting {model_class.__name__} by ID {id_value}: {e}")
        return None


async def get_all(
    db: AsyncSession,
    model_class: Type[T],
    limit: Optional[int] = None,
    offset: Optional[int] = None
) -> List[T]:
    """Type-safe helper to get all records of a model"""
    try:
        stmt: Select[tuple[T]] = select(model_class)
        
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
            
        result: Result[tuple[T]] = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Error getting all {model_class.__name__}: {e}")
        return []


async def get_by_field(
    db: AsyncSession,
    model_class: Type[T],
    field_name: str,
    field_value: Any
) -> Optional[T]:
    """Type-safe helper to get a record by any field"""
    try:
        field = getattr(model_class, field_name)
        stmt: Select[tuple[T]] = select(model_class).where(field == field_value)
        result: Result[tuple[T]] = await db.execute(stmt)
        return result.scalar_one_or_none()
    except AttributeError:
        logger.error(f"Field {field_name} not found on {model_class.__name__}")
        return None
    except Exception as e:
        logger.error(f"Error getting {model_class.__name__} by {field_name}={field_value}: {e}")
        return None


async def get_many_by_field(
    db: AsyncSession,
    model_class: Type[T],
    field_name: str,
    field_value: Any,
    limit: Optional[int] = None
) -> List[T]:
    """Type-safe helper to get multiple records by field value"""
    try:
        field = getattr(model_class, field_name)
        stmt: Select[tuple[T]] = select(model_class).where(field == field_value)
        
        if limit is not None:
            stmt = stmt.limit(limit)
            
        result: Result[tuple[T]] = await db.execute(stmt)
        return list(result.scalars().all())
    except AttributeError:
        logger.error(f"Field {field_name} not found on {model_class.__name__}")
        return []
    except Exception as e:
        logger.error(f"Error getting {model_class.__name__} records by {field_name}={field_value}: {e}")
        return []


async def create_record(
    db: AsyncSession,
    record: T
) -> Optional[T]:
    """Type-safe helper to create a new record"""
    try:
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record
    except Exception as e:
        logger.error(f"Error creating {type(record).__name__}: {e}")
        await db.rollback()
        return None


async def update_record(
    db: AsyncSession,
    model_class: Type[T],
    id_value: str,
    update_data: Dict[str, Any]
) -> Optional[T]:
    """Type-safe helper to update a record by ID"""
    try:
        stmt = update(model_class).where(model_class.id == id_value).values(**update_data)
        await db.execute(stmt)
        await db.commit()
        
        # Return the updated record
        return await get_by_id(db, model_class, id_value)
    except Exception as e:
        logger.error(f"Error updating {model_class.__name__} {id_value}: {e}")
        await db.rollback()
        return None


async def delete_record(
    db: AsyncSession,
    model_class: Type[T],
    id_value: str
) -> bool:
    """Type-safe helper to delete a record by ID"""
    try:
        stmt = delete(model_class).where(model_class.id == id_value)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0
    except Exception as e:
        logger.error(f"Error deleting {model_class.__name__} {id_value}: {e}")
        await db.rollback()
        return False


async def count_records(
    db: AsyncSession,
    model_class: Type[T],
    filter_field: Optional[str] = None,
    filter_value: Optional[Any] = None
) -> int:
    """Type-safe helper to count records"""
    try:
        from sqlalchemy import func
        
        stmt = select(func.count(model_class.id))
        
        if filter_field and filter_value is not None:
            field = getattr(model_class, filter_field)
            stmt = stmt.where(field == filter_value)
            
        result: Result[tuple[int]] = await db.execute(stmt)
        count = result.scalar_one()
        return count if count is not None else 0
    except Exception as e:
        logger.error(f"Error counting {model_class.__name__}: {e}")
        return 0


async def exists_by_id(
    db: AsyncSession,
    model_class: Type[T],
    id_value: str
) -> bool:
    """Type-safe helper to check if a record exists by ID"""
    try:
        from sqlalchemy import exists
        
        stmt = select(exists().where(model_class.id == id_value))
        result: Result[tuple[bool]] = await db.execute(stmt)
        return result.scalar_one() or False
    except Exception as e:
        logger.error(f"Error checking existence of {model_class.__name__} {id_value}: {e}")
        return False


async def get_paginated(
    db: AsyncSession,
    model_class: Type[T],
    page: int = 1,
    page_size: int = 50,
    order_by: Optional[str] = None
) -> Dict[str, Any]:
    """Type-safe helper for paginated queries"""
    try:
        offset = (page - 1) * page_size
        
        # Build base query
        stmt: Select[tuple[T]] = select(model_class)
        
        # Add ordering if specified
        if order_by:
            order_field = getattr(model_class, order_by, None)
            if order_field is not None:
                stmt = stmt.order_by(order_field)
        
        # Add pagination
        stmt = stmt.offset(offset).limit(page_size)
        
        # Execute query
        result: Result[tuple[T]] = await db.execute(stmt)
        records = list(result.scalars().all())
        
        # Get total count
        total = await count_records(db, model_class)
        
        return {
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    except Exception as e:
        logger.error(f"Error getting paginated {model_class.__name__}: {e}")
        return {
            "records": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0
        }
