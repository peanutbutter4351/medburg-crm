"""
Abstract base model providing automatic timestamp fields.

Every concrete model in the project should inherit from BaseModel
so every row carries created_at / updated_at metadata consistently.
"""

from django.db import models


class BaseModel(models.Model):
    """Abstract base with created / updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
