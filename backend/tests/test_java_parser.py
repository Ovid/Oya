"""Java parser tests."""

import pytest

from oya.parsing import SymbolType
from oya.parsing.java_parser import JavaParser


@pytest.fixture
def parser():
    """Create Java parser instance."""
    return JavaParser()


def test_parser_supported_extensions(parser):
    """Parser supports .java files."""
    assert ".java" in parser.supported_extensions


def test_parses_class(parser):
    """Extracts class declaration."""
    code = '''
public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }
}
'''
    result = parser.parse_string(code, "Calculator.java")

    assert result.ok
    class_sym = next(s for s in result.file.symbols if s.symbol_type == SymbolType.CLASS)
    assert class_sym.name == "Calculator"


def test_parses_methods(parser):
    """Extracts class methods."""
    code = '''
public class Service {
    public void doSomething() {}
    private String helper(int value) { return ""; }
}
'''
    result = parser.parse_string(code, "Service.java")

    assert result.ok
    methods = [s for s in result.file.symbols if s.symbol_type == SymbolType.METHOD]
    assert len(methods) == 2
    names = [m.name for m in methods]
    assert "doSomething" in names
    assert "helper" in names


def test_parses_interface(parser):
    """Extracts interface declarations."""
    code = '''
public interface Repository<T> {
    T findById(long id);
    void save(T entity);
}
'''
    result = parser.parse_string(code, "Repository.java")

    assert result.ok
    interface = next(s for s in result.file.symbols if s.symbol_type == SymbolType.INTERFACE)
    assert interface.name == "Repository"


def test_parses_enum(parser):
    """Extracts enum declarations."""
    code = '''
public enum Status {
    PENDING,
    ACTIVE,
    COMPLETED
}
'''
    result = parser.parse_string(code, "Status.java")

    assert result.ok
    enum_sym = next(s for s in result.file.symbols if s.symbol_type == SymbolType.ENUM)
    assert enum_sym.name == "Status"


def test_parses_imports(parser):
    """Extracts import statements."""
    code = '''
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;

public class MyService {}
'''
    result = parser.parse_string(code, "MyService.java")

    assert result.ok
    imports = result.file.imports
    assert any("java.util.List" in imp for imp in imports)
    assert any("springframework" in imp for imp in imports)


def test_parses_annotations(parser):
    """Extracts class and method annotations."""
    code = '''
@Service
@Transactional
public class UserService {
    @GetMapping("/users")
    public List<User> getUsers() {
        return null;
    }
}
'''
    result = parser.parse_string(code, "UserService.java")

    assert result.ok
    class_sym = next(s for s in result.file.symbols if s.symbol_type == SymbolType.CLASS)
    assert "Service" in class_sym.decorators

    # The method with @GetMapping is classified as a ROUTE, so look for that
    route = next(s for s in result.file.symbols if s.symbol_type == SymbolType.ROUTE)
    assert "GetMapping" in route.decorators


def test_identifies_spring_routes(parser):
    """Identifies Spring MVC route handlers."""
    code = '''
@RestController
public class UserController {
    @GetMapping("/api/users")
    public List<User> list() { return null; }

    @PostMapping("/api/users")
    public User create(@RequestBody User user) { return user; }
}
'''
    result = parser.parse_string(code, "UserController.java")

    assert result.ok
    routes = [s for s in result.file.symbols if s.symbol_type == SymbolType.ROUTE]
    assert len(routes) == 2
