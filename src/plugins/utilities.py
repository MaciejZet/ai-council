"""
Utility Plugins
================
Calculator, Date/Time, Hash/Encode, Unit Converter, Random Generator
"""

import hashlib
import base64
import uuid
import random
import string
import math
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from urllib.parse import quote, unquote

from src.plugins import BasePlugin, PluginResult


class CalculatorPlugin(BasePlugin):
    """Kalkulator matematyczny"""
    
    name = "Calculator"
    description = "Obliczenia matematyczne (bezpieczne eval)"
    icon = "🔢"
    category = "utility"
    requires_api_key = False
    
    # Dozwolone funkcje
    SAFE_FUNCTIONS = {
        'abs': abs, 'round': round, 'min': min, 'max': max,
        'sum': sum, 'pow': pow, 'sqrt': math.sqrt,
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
        'log': math.log, 'log10': math.log10, 'exp': math.exp,
        'pi': math.pi, 'e': math.e,
        'floor': math.floor, 'ceil': math.ceil
    }
    
    async def execute(self, expression: str) -> PluginResult:
        """
        Oblicza wyrażenie matematyczne
        
        Args:
            expression: Wyrażenie do obliczenia (np. "2+2", "sqrt(16)")
        """
        try:
            # Wyczyść wyrażenie
            expr = expression.replace('^', '**')
            
            # Sprawdź bezpieczeństwo
            if not self._is_safe(expr):
                return PluginResult(
                    success=False,
                    error="Wyrażenie zawiera niedozwolone elementy",
                    source="calculator"
                )
            
            # Oblicz
            result = eval(expr, {"__builtins__": {}}, self.SAFE_FUNCTIONS)
            
            return PluginResult(
                success=True,
                data={
                    "expression": expression,
                    "result": result,
                    "formatted": f"{expression} = {result}"
                },
                source="calculator"
            )
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"Błąd obliczeń: {str(e)}",
                source="calculator"
            )
    
    def _is_safe(self, expr: str) -> bool:
        """Sprawdza czy wyrażenie jest bezpieczne"""
        # Usuń dozwolone elementy
        allowed = r'[\d\s\+\-\*\/\.\(\)\,\^]'
        for func in self.SAFE_FUNCTIONS:
            expr = expr.replace(func, '')
        expr = re.sub(allowed, '', expr)
        return len(expr) == 0


class DateTimePlugin(BasePlugin):
    """Operacje na datach i czasie"""
    
    name = "Date/Time Utils"
    description = "Konwersje dat, obliczenia, strefy czasowe"
    icon = "📅"
    category = "utility"
    requires_api_key = False
    
    async def execute(
        self, 
        operation: str = "now",
        date1: str = None,
        date2: str = None,
        days: int = 0,
        format: str = "%Y-%m-%d %H:%M:%S"
    ) -> PluginResult:
        """
        Operacje na datach
        
        Args:
            operation: "now", "diff", "add", "format", "parse"
            date1, date2: Daty do operacji
            days: Liczba dni do dodania/odjęcia
            format: Format daty
        """
        try:
            if operation == "now":
                now = datetime.now()
                return PluginResult(
                    success=True,
                    data={
                        "datetime": now.strftime(format),
                        "timestamp": int(now.timestamp()),
                        "iso": now.isoformat(),
                        "weekday": now.strftime("%A"),
                        "week": now.isocalendar()[1]
                    },
                    source="datetime"
                )
            
            elif operation == "diff":
                d1 = datetime.fromisoformat(date1) if date1 else datetime.now()
                d2 = datetime.fromisoformat(date2) if date2 else datetime.now()
                diff = d2 - d1
                
                return PluginResult(
                    success=True,
                    data={
                        "days": diff.days,
                        "seconds": diff.seconds,
                        "total_seconds": diff.total_seconds(),
                        "weeks": diff.days // 7,
                        "hours": diff.total_seconds() / 3600
                    },
                    source="datetime"
                )
            
            elif operation == "add":
                d = datetime.fromisoformat(date1) if date1 else datetime.now()
                result = d + timedelta(days=days)
                
                return PluginResult(
                    success=True,
                    data={
                        "original": d.strftime(format),
                        "result": result.strftime(format),
                        "days_added": days
                    },
                    source="datetime"
                )
            
            else:
                return PluginResult(
                    success=False,
                    error=f"Nieznana operacja: {operation}",
                    source="datetime"
                )
                
        except Exception as e:
            return PluginResult(
                success=False,
                error=f"Date error: {str(e)}",
                source="datetime"
            )


class HashEncodePlugin(BasePlugin):
    """Hashowanie i kodowanie"""
    
    name = "Hash/Encode"
    description = "MD5, SHA, Base64, URL encode/decode"
    icon = "🔐"
    category = "utility"
    requires_api_key = False
    
    async def execute(
        self,
        text: str,
        operation: str = "md5"  # md5, sha256, sha512, base64_encode, base64_decode, url_encode, url_decode
    ) -> PluginResult:
        try:
            result = None
            
            if operation == "md5":
                result = hashlib.md5(text.encode()).hexdigest()
            elif operation == "sha256":
                result = hashlib.sha256(text.encode()).hexdigest()
            elif operation == "sha512":
                result = hashlib.sha512(text.encode()).hexdigest()
            elif operation == "base64_encode":
                result = base64.b64encode(text.encode()).decode()
            elif operation == "base64_decode":
                result = base64.b64decode(text.encode()).decode()
            elif operation == "url_encode":
                result = quote(text)
            elif operation == "url_decode":
                result = unquote(text)
            else:
                return PluginResult(
                    success=False,
                    error=f"Nieznana operacja: {operation}",
                    source="hash"
                )
            
            return PluginResult(
                success=True,
                data={
                    "input": text[:100] + "..." if len(text) > 100 else text,
                    "operation": operation,
                    "result": result
                },
                source="hash"
            )
            
        except Exception as e:
            return PluginResult(
                success=False,
                error=str(e),
                source="hash"
            )


class UnitConverterPlugin(BasePlugin):
    """Przelicznik jednostek"""
    
    name = "Unit Converter"
    description = "Przeliczanie jednostek: długość, waga, temperatura, dane"
    icon = "📏"
    category = "utility"
    requires_api_key = False
    
    CONVERSIONS = {
        # Długość (w metrach)
        "km": 1000, "m": 1, "cm": 0.01, "mm": 0.001,
        "mi": 1609.34, "yd": 0.9144, "ft": 0.3048, "in": 0.0254,
        # Waga (w gramach)
        "kg": 1000, "g": 1, "mg": 0.001,
        "lb": 453.592, "oz": 28.3495,
        # Dane (w bajtach)
        "TB": 1e12, "GB": 1e9, "MB": 1e6, "KB": 1e3, "B": 1,
    }
    
    async def execute(
        self,
        value: float,
        from_unit: str,
        to_unit: str
    ) -> PluginResult:
        try:
            # Temperatura - osobna logika
            if from_unit in ["C", "F", "K"] and to_unit in ["C", "F", "K"]:
                result = self._convert_temperature(value, from_unit, to_unit)
            else:
                # Sprawdź czy jednostki są kompatybilne
                if from_unit not in self.CONVERSIONS or to_unit not in self.CONVERSIONS:
                    return PluginResult(
                        success=False,
                        error=f"Nieznana jednostka: {from_unit} lub {to_unit}",
                        source="converter"
                    )
                
                # Przelicz przez jednostkę bazową
                base_value = value * self.CONVERSIONS[from_unit]
                result = base_value / self.CONVERSIONS[to_unit]
            
            return PluginResult(
                success=True,
                data={
                    "input": f"{value} {from_unit}",
                    "output": f"{result:.6g} {to_unit}",
                    "value": result
                },
                source="converter"
            )
            
        except Exception as e:
            return PluginResult(
                success=False,
                error=str(e),
                source="converter"
            )
    
    def _convert_temperature(self, value: float, from_u: str, to_u: str) -> float:
        # Do Celsjusza
        if from_u == "F":
            celsius = (value - 32) * 5/9
        elif from_u == "K":
            celsius = value - 273.15
        else:
            celsius = value
        
        # Z Celsjusza
        if to_u == "F":
            return celsius * 9/5 + 32
        elif to_u == "K":
            return celsius + 273.15
        return celsius


class RandomGeneratorPlugin(BasePlugin):
    """Generator losowych wartości"""
    
    name = "Random Generator"
    description = "UUID, hasła, liczby losowe, lorem ipsum"
    icon = "🎲"
    category = "utility"
    requires_api_key = False
    
    LOREM = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris."
    
    async def execute(
        self,
        type: str = "uuid",  # uuid, password, number, lorem, string
        length: int = 16,
        min_val: int = 0,
        max_val: int = 100,
        count: int = 1
    ) -> PluginResult:
        try:
            results = []
            
            for _ in range(min(count, 10)):  # Max 10
                if type == "uuid":
                    results.append(str(uuid.uuid4()))
                elif type == "password":
                    chars = string.ascii_letters + string.digits + "!@#$%^&*"
                    results.append(''.join(random.choices(chars, k=length)))
                elif type == "number":
                    results.append(random.randint(min_val, max_val))
                elif type == "float":
                    results.append(round(random.uniform(min_val, max_val), 2))
                elif type == "string":
                    results.append(''.join(random.choices(string.ascii_letters, k=length)))
                elif type == "lorem":
                    words = self.LOREM.split()
                    results.append(' '.join(random.choices(words, k=length)))
                elif type == "hex":
                    results.append(''.join(random.choices('0123456789abcdef', k=length)))
            
            return PluginResult(
                success=True,
                data={
                    "type": type,
                    "count": len(results),
                    "results": results if count > 1 else results[0]
                },
                source="random"
            )
            
        except Exception as e:
            return PluginResult(
                success=False,
                error=str(e),
                source="random"
            )


class TextToolsPlugin(BasePlugin):
    """Narzędzia do przetwarzania tekstu"""
    
    name = "Text Tools"
    description = "Formatowanie, czyszczenie, analiza tekstu"
    icon = "📝"
    category = "utility"
    requires_api_key = False
    
    async def execute(
        self,
        text: str,
        operation: str = "stats"  # stats, upper, lower, title, reverse, clean, words, lines
    ) -> PluginResult:
        try:
            result = {}
            
            if operation == "stats":
                words = text.split()
                result = {
                    "characters": len(text),
                    "characters_no_spaces": len(text.replace(" ", "")),
                    "words": len(words),
                    "lines": text.count('\n') + 1,
                    "sentences": text.count('.') + text.count('!') + text.count('?'),
                    "avg_word_length": sum(len(w) for w in words) / len(words) if words else 0
                }
            elif operation == "upper":
                result = {"text": text.upper()}
            elif operation == "lower":
                result = {"text": text.lower()}
            elif operation == "title":
                result = {"text": text.title()}
            elif operation == "reverse":
                result = {"text": text[::-1]}
            elif operation == "clean":
                # Usuń wielokrotne spacje, trimuj
                cleaned = ' '.join(text.split())
                result = {"text": cleaned}
            elif operation == "words":
                result = {"words": text.split(), "count": len(text.split())}
            elif operation == "lines":
                lines = text.split('\n')
                result = {"lines": lines, "count": len(lines)}
            elif operation == "slug":
                slug = text.lower().replace(' ', '-')
                slug = re.sub(r'[^a-z0-9\-]', '', slug)
                result = {"slug": slug}
            else:
                return PluginResult(
                    success=False,
                    error=f"Nieznana operacja: {operation}",
                    source="text"
                )
            
            return PluginResult(
                success=True,
                data={"operation": operation, **result},
                source="text"
            )
            
        except Exception as e:
            return PluginResult(
                success=False,
                error=str(e),
                source="text"
            )
