from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, Integer, BigInteger, Boolean, ForeignKey, DateTime
from config import DATABASE_URL
from datetime import datetime

engine = create_async_engine(DATABASE_URL)
Base = declarative_base()
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String)
    tg_id = Column(BigInteger, unique=True)
    date = Column(DateTime, default=datetime.now)
    phone = Column(String)


class Driver(Base):
    __tablename__ = 'drivers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    trip = Column(String)
    seats = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)


class RideRequest(Base):
    __tablename__ = 'ride_requests'

    id = Column(Integer, primary_key=True, autoincrement=True)
    passenger_id = Column(Integer, ForeignKey('users.id'))
    driver_id = Column(Integer, ForeignKey('drivers.id'))
    is_accepted = Column(Boolean, default=False)
    is_declined = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    


class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    is_full = Column(Boolean, default=False)
