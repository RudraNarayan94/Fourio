up:
	docker compose up

up-mongo:
	docker compose -f docker-compose.yml -f docker-compose.mongo.yml up

up-hybrid:
	docker compose -f docker-compose.yml -f docker-compose.hybrid.yml up

down:
	docker compose -f docker-compose.yml -f docker-compose.hybrid.yml down --remove-orphans

down-v:
	docker compose -f docker-compose.yml -f docker-compose.hybrid.yml down -v --remove-orphans

logs:
	docker compose logs -f api
