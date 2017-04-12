
init:
	pip install pipenv
	pipenv lock
	pipenv install --dev

test:
	pipenv run py.test tests --tb=short

coverage:
	pipenv run py.test --cov=slingshot --cov-report term-missing tests
