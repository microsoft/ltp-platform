# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Defines the data types used in the Copilot Agent."""

from __future__ import annotations

from pydantic import BaseModel, Field


# defines the design model with fields like target design and base design.
class Design(BaseModel):
    """Defines the design model."""

    Target: str = Field(default=None, description='Target design')
    Baseline: str | None = Field(default=None, description='Base design')


# defines the design model with fields like target design and base design.
class Customer(BaseModel):
    """Defines the design model."""

    Target: str = Field(default=None, description='Target customer')
    Baseline: str | None = Field(default=None, description='Base customer')


# defines the DCW model with fields like design, criterion, workload, and additional data.
class DCW(BaseModel):
    """Defines the DCW model."""

    Design: Design
    Criterion: str | list[str] = Field(..., description='Evaluation Criterion')
    Workload: str = Field(..., description='Workload')
    Customer: Customer
    # AdditionalData: Optional[AdditionalData] #=Field(..., description="additional data")

    def to_dict(self):
        """Check if the user is authorized."""
        return {
            'Design': self.Design.dict(),
            'Criterion': self.Criterion,
            'Workload': self.Workload,
            'Customer': self.Customer.dict(),
        }


