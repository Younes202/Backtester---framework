from sqlalchemy import Column, Integer, Float, DateTime
from connection import Base

class Kline(Base):
    __tablename__ = "klines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    open_time = Column(DateTime, nullable=False)
    close_time = Column(DateTime, nullable=False)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)


class Kline_BTC(Base):
    __tablename__ = "kline_btc"

    id = Column(Integer, primary_key=True, autoincrement=True)
    open_time = Column(DateTime, nullable=False)
    close_time = Column(DateTime, nullable=False)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)

class Kline_BNB(Base):
    __tablename__ = "kline_bnb"

    id = Column(Integer, primary_key=True, autoincrement=True)
    open_time = Column(DateTime, nullable=False)
    close_time = Column(DateTime, nullable=False)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)

class Kline_ADA(Base):
    __tablename__ = "kline_ada"

    id = Column(Integer, primary_key=True, autoincrement=True)
    open_time = Column(DateTime, nullable=False)
    close_time = Column(DateTime, nullable=False)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)

class Kline_ETH(Base):
    __tablename__ = "kline_eth"

    id = Column(Integer, primary_key=True, autoincrement=True)
    open_time = Column(DateTime, nullable=False)
    close_time = Column(DateTime, nullable=False)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)

class Kline_DOT(Base):
    __tablename__ = "kline_dot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    open_time = Column(DateTime, nullable=False)
    close_time = Column(DateTime, nullable=False)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)


class Kline_BTCS(Base):
    __tablename__ = "kline_btcs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    open_time = Column(DateTime, nullable=False)
    close_time = Column(DateTime, nullable=False)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)