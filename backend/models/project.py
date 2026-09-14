from pydantic import BaseModel


class ProjectSpecification(BaseModel):
    project_name: str
    description: str
    languages: list[str]
    technologies: list[str]
    requirements: list[str]
    components: list[str]
    deliverables: list[str]