"""Integration tests for reference extraction."""

import pytest

from oya.parsing import PythonParser, TypeScriptParser, ReferenceType


class TestPythonReferenceExtraction:
    """Test reference extraction on real Python code."""

    @pytest.fixture
    def parser(self):
        return PythonParser()

    def test_extracts_references_from_real_code(self, parser):
        """Parse a realistic Python file and verify reference extraction."""
        code = '''
from typing import Optional
from dataclasses import dataclass

@dataclass
class User:
    """A user entity."""
    name: str
    email: str

class UserService:
    """Service for user operations."""

    def __init__(self, db: Database):
        self.db = db

    def create_user(self, name: str, email: str) -> User:
        """Create a new user."""
        user = User(name=name, email=email)
        self.db.save(user)
        return user

    def find_user(self, email: str) -> Optional[User]:
        """Find user by email."""
        return self.db.query(User).filter_by(email=email).first()
'''
        result = parser.parse_string(code, "user_service.py")

        assert result.ok
        refs = result.file.references

        # Should have imports
        imports = [r for r in refs if r.reference_type == ReferenceType.IMPORTS]
        assert len(imports) >= 2

        # Should have instantiation of User
        instantiations = [r for r in refs if r.reference_type == ReferenceType.INSTANTIATES]
        assert any(r.target == "User" for r in instantiations)

        # Should have method calls
        calls = [r for r in refs if r.reference_type == ReferenceType.CALLS]
        assert any("save" in r.target for r in calls)
        assert any("query" in r.target for r in calls)


class TestTypeScriptReferenceExtraction:
    """Test reference extraction on real TypeScript code."""

    @pytest.fixture
    def parser(self):
        return TypeScriptParser()

    def test_extracts_references_from_real_code(self, parser):
        """Parse a realistic TypeScript file and verify reference extraction."""
        code = """
import { User } from './models';
import { Database } from './database';

export class UserService {
    private db: Database;

    constructor(db: Database) {
        this.db = db;
    }

    async createUser(name: string, email: string): Promise<User> {
        const user = new User(name, email);
        await this.db.save(user);
        return user;
    }

    async findUser(email: string): Promise<User | null> {
        return this.db.query(User).filterBy({ email }).first();
    }
}
"""
        result = parser.parse_string(code, "user_service.ts")

        assert result.ok
        refs = result.file.references

        # Should have instantiation of User via new
        instantiations = [r for r in refs if r.reference_type == ReferenceType.INSTANTIATES]
        assert any(r.target == "User" for r in instantiations)

        # Should have method calls
        calls = [r for r in refs if r.reference_type == ReferenceType.CALLS]
        assert len(calls) > 0
