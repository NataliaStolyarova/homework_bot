REQUIREMENTS_DIR := requirements
FUNCTIONAL_TESTS_DIR := tests


.PHONY: sort
sort:
	isort .


.PHONY: linters
linters:
	black
	flake8
	

.PHONY: test
test:
	pytest --ignore=$(FUNCTIONAL_TESTS_DIR)


.PHONY: req
req:
	cd $(REQUIREMENTS_DIR) && pip install requirements.txt
