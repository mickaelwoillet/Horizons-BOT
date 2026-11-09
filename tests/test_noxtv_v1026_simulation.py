from pathlib import Path
import ast
SRC = Path(__file__).resolve().parents[1] / 'cogs' / 'nox_tv.py'
def test_simulation_staff_private_read_only():
    code = SRC.read_text()
    assert "name='simulation'" in code
    method = code.split('async def simulation(', 1)[1].split('    @noxtv.command', 1)[0]
    assert 'ephemeral=True' in method
    assert 'await self.publish(' not in method
    assert 'INSERT INTO' not in method
    assert 'UPDATE noxtv' not in method
    assert 'DELETE FROM' not in method
def test_module_syntax():
    ast.parse(SRC.read_text())
