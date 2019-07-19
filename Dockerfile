FROM python:3.7-alpine AS alpine
RUN pip install --upgrade pip
RUN apk --no-cache add build-base postgresql-dev
RUN pip install pipenv

FROM alpine AS wheel
COPY . /slingshot/
RUN cd /slingshot && python setup.py bdist_wheel

FROM alpine
COPY Pipfile* /
RUN pipenv install --system --ignore-pipfile --deploy
COPY --from=wheel /slingshot/dist/slingshot-*-py3-none-any.whl .
RUN pip install slingshot-*-py3-none-any.whl
COPY entrypoint.sh /

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]
