"""Pydantic models for meeting room booking system."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel

class Building(BaseModel):
    id:int 
    name:str
    address:str | None=None


class Room(BaseModel):
    id:int
    name:str
    building_id:int 
    floor:int
    capacity:int
    equipment:list [str]=[]

class Booking(BaseModel):
    id:int
    room_id:int
    booked_by:str
    title:str
    date:date
    start_time:time
    end_time:time
    created_at:datetime


class ConflictDetail(BaseModel):
    booking_id:int
    room_id:int
    room_name:str
    booked_by:str
    date:str
    start_time:str
    end_time:str
    title:str


class BookingResult(BaseModel):
    success:bool
    blocking:Booking|None=None
    conflict:ConflictDetail|None=None
    alternatives_hint:dict[str,Any]|None=None


class TimeSlot(BaseModel):
    """A free time slot"""
    start_time:time
    end_time:time