PYTHON = python3
TARGET = er-afd
SRC = er_afd.py

ER ?= (a|b)*abb
CADENA ?= aabb

.PHONY: all config build run test clean

all: build

config:
	@echo "Verificando entorno Python 3..."
	@$(PYTHON) --version
	@echo "Configuración completada."

build:
	@echo "Generando ejecutable '$(TARGET)'..."
	@cp $(SRC) $(TARGET)
	@chmod +x $(TARGET)
	@echo "Compilación lista. Ejecuta con: ./$(TARGET) \"<ER>\" \"<cadena>\""

run: build
	@./$(TARGET) "$(ER)" "$(CADENA)"; \
	CODE=$$?; \
	echo "Código de retorno del programa: $$CODE"

test:
	@$(PYTHON) -m pytest -v test_er_afd.py

clean:
	@echo "Limpiando binarios y archivos temporales..."
	@rm -f $(TARGET)
	@rm -rf __pycache__ .pytest_cache
	@echo "Limpieza completada."