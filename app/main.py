
import json
import os

import redis
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field


# Создаём приложение FastAPI
app = FastAPI(
    title="Fleet Management",
    description="Система управления автопарком",
    version="1.0.0"
)


# Настройки подключения к Redis
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=0,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2
)

# Ключ кеша и время его хранения
CACHE_KEY = "fleet:vehicles"
CACHE_TTL = 30


# Описываем структуру данных автомобиля
class Vehicle(BaseModel):
    brand: str = Field(min_length=1, max_length=50)
    model: str = Field(min_length=1, max_length=50)
    year: int = Field(ge=1980, le=2100)
    plate_number: str = Field(min_length=3, max_length=15)
    mileage_km: int = Field(ge=0, default=0)
    last_service_km: int = Field(ge=0, default=0)
    service_interval_km: int = Field(ge=1000, le=100000, default=10000)
    status: str = "available"


# Временное хранилище автомобилей
vehicles = {}

# Счётчик для присвоения автомобилям ID
next_id = 1


# Функция удаления устаревшего кеша
def invalidate_vehicle_cache():
    try:
        redis_client.delete(CACHE_KEY)
    except redis.RedisError:
        pass


# Главная страница
@app.get("/")
def home():
    return {
        "message": "Fleet Management API is running"
    }


# Проверка работоспособности приложения и Redis
@app.get("/health")
def health():
    try:
        redis_client.ping()
        return {
            "status": "healthy",
            "redis": "connected"
        }
    except redis.RedisError:
        raise HTTPException(
            status_code=503,
            detail="Redis is unavailable"
        )


# Проверка автомобилей, которым требуется техническое обслуживание
@app.post("/maintenance/check")
def check_maintenance():

    checked = 0
    due_vehicles = []

    # Проверяем каждый автомобиль
    for vehicle in vehicles.values():

        checked += 1

        # Рассчитываем пробег после последнего обслуживания
        mileage_since_service = (
            vehicle["mileage_km"] -
            vehicle.get("last_service_km", 0)
        )

        # Получаем установленный интервал обслуживания
        service_interval = vehicle.get(
            "service_interval_km", 10000
        )

        # Проверяем, не пора ли отправить автомобиль на обслуживание
        if mileage_since_service >= service_interval:

            vehicle["status"] = "maintenance_required"

            due_vehicles.append({
                "id": vehicle["id"],
                "brand": vehicle["brand"],
                "model": vehicle["model"],
                "plate_number": vehicle["plate_number"],
                "mileage_since_service": mileage_since_service
            })

    # Обновляем кеш списка автомобилей
    if due_vehicles:
        invalidate_vehicle_cache()

    return {
        "checked": checked,
        "maintenance_required": len(due_vehicles),
        "vehicles": due_vehicles
    }
    return {
        "status": "healthy",
        "redis": "connected"
    }


# Получение списка автомобилей с использованием кеша
@app.get("/vehicles")
def get_vehicles(response: Response):

    # Пробуем получить список из Redis
    try:
        cached_data = redis_client.get(CACHE_KEY)
    except redis.RedisError:
        response.headers["X-Cache"] = "BYPASS"
        return list(vehicles.values())

    # Если данные найдены в кеше
    if cached_data is not None:
        response.headers["X-Cache"] = "HIT"
        return json.loads(cached_data)

    # Если кеш пуст, берём данные из приложения
    result = list(vehicles.values())

    # Сохраняем результат в Redis на 30 секунд
    try:
        redis_client.setex(
            CACHE_KEY,
            CACHE_TTL,
            json.dumps(result, ensure_ascii=False)
        )
        response.headers["X-Cache"] = "MISS"
    except redis.RedisError:
        response.headers["X-Cache"] = "BYPASS"

    return result


# Добавление нового автомобиля
@app.post("/vehicles")
def add_vehicle(vehicle: Vehicle):
    global next_id

    vehicle_data = vehicle.model_dump()
    vehicle_data["id"] = next_id

    vehicles[next_id] = vehicle_data
    next_id += 1

    # Сбрасываем кеш после добавления
    invalidate_vehicle_cache()

    return vehicle_data


# Получение автомобиля по ID
@app.get("/vehicles/{vehicle_id}")
def get_vehicle(vehicle_id: int):
    if vehicle_id not in vehicles:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found"
        )

    return vehicles[vehicle_id]


# Удаление автомобиля
@app.delete("/vehicles/{vehicle_id}")
def delete_vehicle(vehicle_id: int):
    if vehicle_id not in vehicles:
        raise HTTPException(
            status_code=404,
            detail="Vehicle not found"
        )

    del vehicles[vehicle_id]

    # Сбрасываем кеш после удаления
    invalidate_vehicle_cache()

    return {
        "message": "Vehicle deleted successfully"
    }
