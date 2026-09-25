from typing import Literal

from pydantic import BaseModel, Field, model_validator

EntityType = Literal["Company", "Subsidiary", "Contract", "Customer", "Account", "AuditFinding", "Risk"]
RelationType = Literal["owns", "signs", "hasCounterparty", "affects", "relatesTo"]
RELATIONS = {"owns": ("Company", "Subsidiary"), "signs": ("Company", "Contract"),
             "hasCounterparty": ("Contract", "Customer"), "affects": ("Contract", "Account"),
             "relatesTo": ("AuditFinding", "Risk")}


class Entity(BaseModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.:-]+$")
    name: str = Field(min_length=1, max_length=200)
    type: EntityType


class Relation(BaseModel):
    source: str
    target: str
    type: RelationType
    evidence: str = Field(min_length=1, max_length=3000)


class GraphExtraction(BaseModel):
    entities: list[Entity] = Field(max_length=100)
    relations: list[Relation] = Field(max_length=200)

    @model_validator(mode="after")
    def grounded_schema(self):
        entities = {e.id: e for e in self.entities}
        if len(entities) != len(self.entities):
            raise ValueError("Entity IDs must be unique")
        for r in self.relations:
            if r.source not in entities or r.target not in entities:
                raise ValueError("Relation endpoints must exist")
            if (entities[r.source].type, entities[r.target].type) != RELATIONS[r.type]:
                raise ValueError(f"Invalid endpoint types for {r.type}")
        return self


class GraphQuery(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    entity: str = Field(min_length=1, max_length=200)
    hops: int = Field(default=2, ge=1, le=3)
    limit: int = Field(default=10, ge=1, le=30)
    generate_answer: bool = False
