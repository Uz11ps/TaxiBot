from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime
import os
import sys

# Получаем путь к корневой директории проекта
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone_number = Column(String(20))
    registration_date = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Связи
    orders = relationship("Order", back_populates="client")
    reviews = relationship("Review", back_populates="client")

class Driver(Base):
    __tablename__ = 'drivers'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    first_name = Column(String(100), nullable=False)
    license_number = Column(String(50), nullable=False)
    car_registration = Column(String(50), nullable=False)
    car_number = Column(String(20), nullable=False)
    car_photos = Column(Text)  # JSON строка с URL фотографий
    status = Column(String(20), default="OFF_DUTY")
    is_approved = Column(Boolean, default=False)
    registration_date = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Связи
    orders = relationship("Order", back_populates="driver")
    reviews = relationship("Review", back_populates="driver")
    earnings = relationship("Earning", back_populates="driver")

class Order(Base):
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('users.id'))
    driver_id = Column(Integer, ForeignKey('drivers.id'), nullable=True)
    from_address = Column(String(255), nullable=False)
    to_address = Column(String(255), nullable=False)
    comment = Column(Text)
    price = Column(Float, nullable=True)
    counter_offer = Column(Float, nullable=True)
    status = Column(String(20), default="NEW")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Связи
    client = relationship("User", back_populates="orders")
    driver = relationship("Driver", back_populates="orders")
    review = relationship("Review", back_populates="order", uselist=False)

class Review(Base):
    __tablename__ = 'reviews'
    
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), unique=True)
    client_id = Column(Integer, ForeignKey('users.id'))
    driver_id = Column(Integer, ForeignKey('drivers.id'))
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Связи
    order = relationship("Order", back_populates="review")
    client = relationship("User", back_populates="reviews")
    driver = relationship("Driver", back_populates="reviews")

class Earning(Base):
    __tablename__ = 'earnings'
    
    id = Column(Integer, primary_key=True)
    driver_id = Column(Integer, ForeignKey('drivers.id'))
    order_id = Column(Integer, ForeignKey('orders.id'), unique=True)
    amount = Column(Float, nullable=False)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Связи
    driver = relationship("Driver", back_populates="earnings")

def init_db():
    Base.metadata.create_all(engine)

if __name__ == "__main__":
    init_db()