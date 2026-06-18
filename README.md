# cupdate

Python requirements.txt updater.

## Installation

```bash
pip install cupdate
```

## Usage

### Basic Update

```bash
# Update all packages in requirements.txt
cupdate
```

### With Exclusions

Create a `cupdate.config.txt` file to exclude packages:

```
# cupdate.config.txt
numpy
pandas==1.5.0
tensorflow
```

Then run:
```bash
cupdate
```

## Features

- **Smart Updates** - Preserves version operators (>=, <=, ==)
- **Package Exclusions** - Skip specific packages from updates
- **Release Information** - Shows package age and project URLs
- **Formatted Output** - Clean table display of updates
- **PyPI Integration** - Fetches latest versions and metadata

## Example Output

```
NAME         OLD      NEW      AGE        INFO
------------ -------- -------- ---------- -------------------------
requests     2.28.1   2.31.0   2 months   https://pypi.org/project/requests/
flask        2.2.2    3.0.0    3 weeks    https://pypi.org/project/flask/
numpy        1.24.0   1.26.2   1 month    https://pypi.org/project/numpy/

✨ requirements.txt updated with 3 packages
```

## Configuration

### Exclusion File Format

```
# Lines starting with # are comments
package-name
another-package>=1.0.0
specific-version==2.1.0
```

### Version Operators

cupdate preserves your version constraints:

- `package==1.0.0` → `package==1.2.0` (exact version)
- `package>=1.0.0` → `package>=1.2.0` (minimum version)
- `package<=2.0.0` → `package<=2.1.0` (maximum version)

## Requirements File Support

Works with standard `requirements.txt` format:

```
# requirements.txt
requests==2.28.1
flask>=2.2.0
numpy<=1.24.0
pandas
```

## Command Line Interface

```bash
# Update requirements in current directory
cupdate

# The tool automatically looks for:
# - requirements.txt (required)
# - cupdate.config.txt (optional exclusions)
```

## Error Handling

- **Missing requirements.txt** - Shows error and exits
- **Network issues** - Shows warnings, continues with available data  
- **Invalid packages** - Skips problematic packages with warnings
- **Missing exclusions** - Continues normally, updates all packages

## Integration Examples

### CI/CD Pipeline

```yaml
# .github/workflows/update-deps.yml
name: Update Dependencies
on:
  schedule:
    - cron: '0 0 * * 1'  # Weekly on Monday

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install cupdate
        run: pip install cupdate
      - name: Update requirements
        run: cupdate
      - name: Create PR
        # ... create pull request with changes
```

## Development Workflow

```bash
# 1. Install cupdate
pip install cupdate

# 2. Create exclusions (optional)
echo "tensorflow" > cupdate.config.txt

# 3. Update dependencies
cupdate

# 4. Install updated packages
pip install -r requirements.txt

# 5. Test your application
python -m pytest
```

## Package Information

The tool provides rich information about updates:

- **Package Name** - The package being updated
- **Old Version** - Current version in requirements.txt
- **New Version** - Latest available version
- **Age** - How long ago the new version was released
- **Info URL** - Link to package homepage or PyPI page

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests to our repository.

## License

MIT
