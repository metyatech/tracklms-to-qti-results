# Contributing

Thanks for taking the time to contribute!

## Development setup
- Python 3.11+
- Create and activate a virtual environment
- Install dev tools: `python -m pip install -r requirements-dev.txt`

## Running tests
`python -m unittest discover -s tests`

## Linting
`python -m ruff check .`

## Type checking
`python -m pyright src`

## Documentation
Update README and docs when changes affect behavior, inputs, or outputs.

## Pull requests
- Keep changes focused and well described.
- Add or update tests for behavior changes.
- Ensure CI passes before requesting review.
