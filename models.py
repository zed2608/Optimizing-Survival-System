from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class PlantingEvent(Base):
    __tablename__ = "planting_events"

    event_id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String, index=True)
    target_hectares = Column(Float)
    
    # Captures the landowner constraints (e.g., "Fruit-bearing only", "Mixed")
    landowner_preference = Column(String, default="Mixed") 
    
    status = Column(String, default="Planned")
    date_created = Column(DateTime, default=datetime.utcnow)

    # Links this event to all the trees assigned to it
    allocations = relationship("TreeAllocation", back_populates="event")


class TreeAllocation(Base):
    __tablename__ = "tree_allocations"

    tree_id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("planting_events.event_id"))
    
    species_name = Column(String, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Stores the output from the Random Forest model
    suitability_score = Column(Float) 
    
    # If True, this is a pre-existing tree. The system will draw a 5m exclusion zone around it.
    is_baseline_tree = Column(Boolean, default=False) 

    event = relationship("PlantingEvent", back_populates="allocations")