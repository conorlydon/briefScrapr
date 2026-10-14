from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


ShortItem = Annotated[str, StringConstraints(max_length=80)]
BriefList = Annotated[list[ShortItem], Field(max_length=10)]


class ProjectSpecification(BaseModel):
    project_name: str
    description: str
    languages: list[str]
    technologies: list[str]
    requirements: list[str]
    components: list[str]
    deliverables: list[str]


class SectionSpecification(ProjectSpecification):
    project_name: str = Field(max_length=100)
    description: str = Field(max_length=240)
    languages: BriefList
    technologies: BriefList
    requirements: BriefList
    components: BriefList
    deliverables: BriefList
