"""Defines the data types used in the Copilot Agent."""

from __future__ import annotations

from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field


# defines the benchmark model with fields like name, parameters, reason, target, and hardware.
class Benchmark(BaseModel):
    """Defines the benchmark model."""

    name: str = Field(..., description='benchmark name')
    parameters: str | dict = Field('default', description='benchmark parameters')
    reason: str | None = Field(..., description='benchmark reason')
    target: str | None = Field(..., description='benchmark target')
    hardware: str = Field(..., description='benchmark hardware')

    class Config:
        """Pydantic configuration."""

        extra = 'allow'  # Allow arbitrary fields


# defines a list of benchmarks and additional benchmark requirements.
class BList(BaseModel):
    """Defines a list of benchmarks and additional benchmark requirements."""

    benchmarks: list[Benchmark] = Field(..., description='benchmark list')
    additional_benchmark_requirement: list[dict] | None = Field(
        description='additional benchmark requirement', default=None
    )


# parses the blist model using PydanticOutputParser.
Default_blist_parser = PydanticOutputParser(pydantic_object=BList)


# defines the hardware specifications model with fields like SKU, GPU, GPU vendor, ... and setting.
class HardwareSpec(BaseModel):
    """Defines the hardware specifications model."""

    SKU: str = ''
    GPU: str
    GPU_vendor: str
    Number_of_GPUs: str = ''
    GPU_Memory: str = ''
    GPU_Memory_Bandwidth: str = ''
    Interconnect: dict[str, str] = {}
    Tensor_Core_Performance: dict[str, str] = {}
    Infiniband_Interconnect: str = ''
    CPU: str = ''
    Disk: str = ''
    Setting: str = ''

    class Config:
        """Pydantic configuration."""

        extra = 'allow'  # Allow arbitrary fields


# defines the system data model with fields like new hardware specification, baseline hardware specification, and new feature.
class SystemData(BaseModel):
    """Defines the system data model."""

    NewHardwareSpec: HardwareSpec | None
    BaselineHardwareSpec: HardwareSpec | None
    NewFeature: str | None = Field(default=None, description='New feature or new optimization of the new hardware')


# defines the additional data model with fields like non-performance data for analysis and system data.
class AdditionalData(BaseModel):
    """Defines the additional data model."""

    NonePerfData: str | None = Field(..., description='Additional none-performance data for analysis')
    SystemData: SystemData  # = Field(..., description="Hardware specs")


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


# parses the DCW model using PydanticOutputParser.
Default_dcw_parser = PydanticOutputParser(pydantic_object=DCW)
