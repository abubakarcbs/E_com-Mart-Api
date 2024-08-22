from contextlib import asynccontextmanager
from app.db import create_tables, get_session
from model import ProductUpdate, Products
from sqlalchemy import select
from fastapi import Depends, FastAPI, HTTPException, Query
from typing import Annotated, List

from sqlmodel import Session


@asynccontextmanager
async def lifespan(app: FastAPI):
    print('Creating Tables')
    create_tables()
    print("Tables Created")
    yield

app = FastAPI(
    lifespan=lifespan, title="Product Page", version='1.0.0'
)

@app.get("/")
def welcome():
    return {"welcome": "Product Page"}


#  ADD product
@app.post("/products")
def create_product(product: Products, session: Session = Depends(get_session)):
        session.add(product)
        session.commit()
        return {"message": "Product created successfully"}

#  update product

@app.put("/products/{product_id}")
def update_product(product_id: int, product_update: ProductUpdate, session: Session = Depends(get_session)):
    product = session.get(Products, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for key, value in product_update.dict().items():
        setattr(product, key, value)
    session.commit()
    return {"message": "Product updated successfully"}

 # get all products
# @app.get("/products",response_model=List[Products])
# def get_all_products(session: Session = Depends(get_session)):
#     products = session.exec(select(Products)).all()
#     return products
    
# # GET Single Product
@app.get("/products/{product_id}")
def get_product(product_id: int, session: Session = Depends(get_session)):
        product = session.get(Products, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return product

# # Delete product
@app.delete("/products/{product_id}")
def delete_product(product_id: int, session: Session = Depends(get_session)):
        product = session.get(Products, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        session.delete(product)
        session.commit()
        return {"message": "Product deleted successfully"}

