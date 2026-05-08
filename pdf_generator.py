import os
import sys
import json
import csv
import platform
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional

# Проверка версии Python
if sys.version_info < (3, 8):
    print("Требуется Python 3.8 или выше")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("Установите pandas: pip install pandas")
    sys.exit(1)

try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except ImportError:
    print("Установите weasyprint: pip install weasyprint")
    sys.exit(1)


class PDFGenerator:
    """Класс для генерации PDF документов"""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        self.templates_dir = self.base_dir / "templates"
        self.output_dir = self.base_dir / "output"

        # Инициализация директорий
        self._init_directories()

        # Конфигурация шрифтов для кириллицы
        self.font_config = self._setup_fonts()

    def _init_directories(self):
        """Создание необходимых директорий"""
        for directory in [self.data_dir, self.templates_dir, self.output_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"✓ Директория проверена: {directory.name}")

    def _setup_fonts(self) -> FontConfiguration:
        """Настройка шрифтов для поддержки кириллицы"""
        font_config = FontConfiguration()

        # CSS для подключения шрифтов с поддержкой кириллицы
        self.css_string = """
        @page {
            size: A4;
            margin: 2cm;
        }

        @font-face {
            font-family: 'DejaVu Sans';
            src: url('https://github.com/google/fonts/raw/main/apache/dejavusans/DejaVuSans.ttf');
            font-weight: normal;
            font-style: normal;
        }

        @font-face {
            font-family: 'DejaVu Sans';
            src: url('https://github.com/google/fonts/raw/main/apache/dejavusans/DejaVuSans-Bold.ttf');
            font-weight: bold;
            font-style: normal;
        }

        body {
            font-family: 'DejaVu Sans', 'Roboto', 'Arial Unicode MS', sans-serif;
            font-size: 12pt;
            line-height: 1.5;
            color: #333;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }

        th, td {
            border: 1px solid #ddd;
            padding: 8px 12px;
            text-align: left;
            word-wrap: break-word;
            overflow-wrap: break-word;
            hyphens: auto;
        }

        th {
            background-color: #f2f2f2;
            font-weight: bold;
            text-align: center;
        }

        td {
            vertical-align: top;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #333;
            padding-bottom: 20px;
        }

        .header h1 {
            margin: 0;
            font-size: 24pt;
            color: #333;
        }

        .header h2 {
            margin: 10px 0 0 0;
            font-size: 16pt;
            color: #666;
        }

        .invoice-details {
            margin-bottom: 30px;
        }

        .invoice-details table {
            width: auto;
            min-width: 50%;
        }

        .invoice-details td:first-child {
            font-weight: bold;
            background-color: #f9f9f9;
            width: 30%;
        }

        .total {
            text-align: right;
            font-size: 14pt;
            font-weight: bold;
            margin-top: 20px;
            padding: 10px;
            border-top: 2px solid #333;
        }

        /* Для длинных строк в таблицах */
        .wrap-text {
            word-wrap: break-word;
            overflow-wrap: break-word;
            max-width: 300px;
        }
        """

        return font_config

    def get_csv_files(self) -> List[Path]:
        """Получение списка CSV файлов"""
        return sorted(self.data_dir.glob("*.csv"))

    def get_json_files(self) -> List[Path]:
        """Получение списка JSON файлов"""
        return sorted(self.data_dir.glob("*.json"))

    def get_template_files(self) -> List[Path]:
        """Получение списка HTML шаблонов"""
        return sorted(self.templates_dir.glob("*.html"))

    def load_csv_data(self, filepath: Path) -> pd.DataFrame:
        """Загрузка данных из CSV файла"""
        try:
            # Пробуем разные кодировки
            for encoding in ['utf-8', 'utf-8-sig', 'cp1251', 'windows-1251']:
                try:
                    df = pd.read_csv(filepath, encoding=encoding)
                    return df
                except UnicodeDecodeError:
                    continue
            raise ValueError(f"Не удалось определить кодировку файла {filepath.name}")
        except Exception as e:
            print(f"✗ Ошибка при чтении CSV: {e}")
            return pd.DataFrame()

    def load_json_data(self, filepath: Path) -> List[Dict[str, Any]]:
        """Загрузка данных из JSON файла"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Если данные в формате списка словарей
                if isinstance(data, list):
                    return data
                # Если данные в формате словаря
                elif isinstance(data, dict):
                    return [data]
                else:
                    print("✗ Неверный формат JSON данных")
                    return []
        except Exception as e:
            print(f"✗ Ошибка при чтении JSON: {e}")
            return []

    def get_invoice_ids(self, data: Any, file_type: str) -> List[str]:
        """Получение списка invoice_id из данных"""
        if file_type == 'csv':
            if isinstance(data, pd.DataFrame):
                if 'invoice_id' in data.columns:
                    return data['invoice_id'].unique().tolist()
                elif 'Invoice_ID' in data.columns:
                    return data['Invoice_ID'].unique().tolist()
        elif file_type == 'json':
            if isinstance(data, list):
                ids = set()
                for item in data:
                    if 'invoice_id' in item:
                        ids.add(item['invoice_id'])
                    elif 'Invoice_ID' in item:
                        ids.add(item['Invoice_ID'])
                return list(ids)

        return []

    def filter_data_by_invoice(self, data: Any, invoice_id: str, file_type: str) -> Any:
        """Фильтрация данных по invoice_id"""
        if file_type == 'csv':
            if isinstance(data, pd.DataFrame):
                col_name = 'invoice_id' if 'invoice_id' in data.columns else 'Invoice_ID'
                return data[data[col_name] == invoice_id]
        elif file_type == 'json':
            if isinstance(data, list):
                return [item for item in data if item.get('invoice_id') == invoice_id or
                        item.get('Invoice_ID') == invoice_id]

        return data

    def render_html_template(self, template_path: Path, data: Any, file_type: str) -> str:
        """Рендеринг HTML шаблона с подстановкой данных"""
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()

            # Если CSV - преобразуем в список словарей
            if file_type == 'csv' and isinstance(data, pd.DataFrame):
                records = data.to_dict('records')
                if len(records) > 0:
                    # Группируем данные для шаблона
                    invoice_data = records[0].copy()
                    # Добавляем все строки как items
                    invoice_data['items'] = records
                    # Вычисляем общую сумму
                    if 'amount' in data.columns:
                        invoice_data['total'] = data['amount'].sum()
                    elif 'Amount' in data.columns:
                        invoice_data['total'] = data['Amount'].sum()
                    else:
                        invoice_data['total'] = 0
                else:
                    invoice_data = {}
            else:
                # JSON данные
                if isinstance(data, list) and len(data) > 0:
                    invoice_data = data[0].copy()
                    invoice_data['items'] = data
                    # Вычисляем сумму если есть amount
                    if all('amount' in item for item in data):
                        invoice_data['total'] = sum(item.get('amount', 0) for item in data)
                    elif all('Amount' in item for item in data):
                        invoice_data['total'] = sum(item.get('Amount', 0) for item in data)
                    else:
                        invoice_data['total'] = 0
                else:
                    invoice_data = data if isinstance(data, dict) else {}

            # Замена плейсхолдеров {{ key }}
            rendered = template
            for key, value in invoice_data.items():
                placeholder = f"{{{{ invoice.{key} }}}}"
                if placeholder in rendered:
                    rendered = rendered.replace(placeholder, str(value) if value is not None else "")

                # Также проверяем простые плейсхолдеры {{ key }}
                placeholder_simple = f"{{{{ {key} }}}}"
                if placeholder_simple in rendered:
                    rendered = rendered.replace(placeholder_simple, str(value) if value is not None else "")

            # Обработка items для таблицы
            if 'items' in invoice_data:
                items_html = self._generate_items_table(invoice_data['items'])
                rendered = rendered.replace("{{ items_table }}", items_html)

            return rendered

        except Exception as e:
            print(f"✗ Ошибка при рендеринге шаблона: {e}")
            return ""

    def _generate_items_table(self, items: List[Dict]) -> str:
        """Генерация HTML таблицы для элементов"""
        if not items:
            return ""

        html = "<table><thead><tr>"

        # Заголовки таблицы
        headers = {
            'item_name': 'Наименование',
            'itemName': 'Наименование',
            'name': 'Наименование',
            'quantity': 'Количество',
            'qty': 'Количество',
            'price': 'Цена',
            'unit_price': 'Цена за ед.',
            'amount': 'Сумма',
            'total': 'Сумма',
            'number': '№',
            '№': '№'
        }

        # Определяем колонки из первого элемента
        first_item = items[0]
        columns = list(first_item.keys())

        for col in columns:
            header_name = headers.get(col, col.replace('_', ' ').title())
            html += f"<th>{header_name}</th>"

        html += "</tr></thead><tbody>"

        # Строки таблицы
        for idx, item in enumerate(items, 1):
            html += "<tr>"
            if 'number' not in columns and '№' not in columns:
                html += f"<td>{idx}</td>"

            for col in columns:
                value = item.get(col, '')
                # Форматирование чисел
                if isinstance(value, (int, float)) and col in ['price', 'amount', 'total', 'unit_price']:
                    value = f"{value:,.2f} ₽"
                html += f"<td class='wrap-text'>{value}</td>"

            html += "</tr>"

        html += "</tbody></table>"
        return html

    def generate_pdf(self, html_content: str, output_path: Path):
        """Генерация PDF из HTML"""
        try:
            # Создаем CSS объект
            css = CSS(string=self.css_string, font_config=self.font_config)

            # Генерируем PDF
            HTML(string=html_content).write_pdf(
                output_path,
                stylesheets=[css],
                font_config=self.font_config
            )

            print(f"✓ PDF успешно создан: {output_path.name}")
            return True

        except Exception as e:
            print(f"✗ Ошибка при генерации PDF: {e}")
            print("💡 Убедитесь, что установлены все зависимости WeasyPrint")
            return False

    def open_pdf(self, pdf_path: Path):
        """Автоматическое открытие PDF в системной программе"""
        try:
            system = platform.system()

            if system == 'Windows':
                os.startfile(pdf_path)
            elif system == 'Darwin':  # macOS
                subprocess.run(['open', pdf_path], check=True)
            else:  # Linux
                subprocess.run(['xdg-open', pdf_path], check=True)

            print(f"✓ PDF открыт в программе просмотра")

        except Exception as e:
            print(f"⚠ Не удалось автоматически открыть PDF: {e}")
            print(f"📁 Файл сохранен: {pdf_path}")

    def display_menu(self, items: List, title: str) -> Optional[int]:
        """Отображение меню выбора"""
        print(f"\n{'=' * 60}")
        print(f"{title}")
        print('=' * 60)

        if not items:
            print("✗ Нет доступных элементов")
            return None

        for idx, item in enumerate(items, 1):
            if isinstance(item, Path):
                print(f"{idx}. {item.name}")
            else:
                print(f"{idx}. {item}")

        print(f"0. Выход")
        print('=' * 60)

        while True:
            try:
                choice = input("\nВыберите номер (0 для выхода): ").strip()
                choice_num = int(choice)

                if choice_num == 0:
                    return None
                elif 1 <= choice_num <= len(items):
                    return choice_num - 1  # Индекс с 0
                else:
                    print(f"✗ Введите число от 0 до {len(items)}")
            except ValueError:
                print("✗ Введите корректное число")

    def run(self):
        """Основной цикл программы"""
        print("\n" + "=" * 60)
        print("  PDF GENERATOR - Генератор PDF документов")
        print("  Поддержка кириллицы | Windows/macOS")
        print("=" * 60)

        # Получаем списки файлов
        csv_files = self.get_csv_files()
        json_files = self.get_json_files()
        templates = self.get_template_files()

        all_data_files = csv_files + json_files

        if not all_data_files:
            print(f"\n✗ В директории {self.data_dir} нет файлов CSV или JSON")
            print("💡 Добавьте файлы с данными и попробуйте снова")
            return

        if not templates:
            print(f"\n✗ В директории {self.templates_dir} нет HTML шаблонов")
            print("💡 Добавьте HTML шаблоны и попробуйте снова")
            return

        # Выбор файла с данными
        data_idx = self.display_menu(all_data_files, "📁 ДОСТУПНЫЕ ФАЙЛЫ С ДАННЫМИ")
        if data_idx is None:
            print("\n👋 Завершение работы...")
            return

        selected_data_file = all_data_files[data_idx]
        file_type = 'csv' if selected_data_file.suffix.lower() == '.csv' else 'json'
        print(f"\n✓ Выбран файл: {selected_data_file.name} ({file_type.upper()})")

        # Загрузка данных
        print("\n⏳ Загрузка данных...")
        if file_type == 'csv':
            data = self.load_csv_data(selected_data_file)
        else:
            data = self.load_json_data(selected_data_file)

        # Получение списка invoice_id
        invoice_ids = self.get_invoice_ids(data, file_type)

        if not invoice_ids:
            print("\n✗ Не найдены invoice_id в файле")
            print("💡 Убедитесь, что файл содержит колонку 'invoice_id'")
            return

        # Выбор invoice_id
        invoice_idx = self.display_menu(invoice_ids, "📋 ДОСТУПНЫЕ СЧЕТА (INVOICE ID)")
        if invoice_idx is None:
            print("\n👋 Завершение работы...")
            return

        selected_invoice_id = invoice_ids[invoice_idx]
        print(f"\n✓ Выбран счет: {selected_invoice_id}")

        # Фильтрация данных по invoice_id
        filtered_data = self.filter_data_by_invoice(data, selected_invoice_id, file_type)

        # Выбор шаблона
        template_idx = self.display_menu(templates, " ДОСТУПНЫЕ HTML ШАБЛОНЫ")
        if template_idx is None:
            print("\n👋 Завершение работы...")
            return

        selected_template = templates[template_idx]
        print(f"\n✓ Выбран шаблон: {selected_template.name}")

        # Рендеринг HTML
        print("\n⏳ Рендеринг HTML...")
        html_content = self.render_html_template(selected_template, filtered_data, file_type)

        if not html_content:
            print("\n✗ Ошибка при рендеринге HTML")
            return

        # Генерация имени выходного файла
        output_filename = f"invoice_{selected_invoice_id}.pdf"
        output_path = self.output_dir / output_filename

        # Генерация PDF
        print("\n⏳ Генерация PDF...")
        if not self.generate_pdf(html_content, output_path):
            return

        # Автоматическое открытие PDF
        print("\n⏳ Открытие PDF...")
        self.open_pdf(output_path)

        print("\n" + "=" * 60)
        print("  ✅ Готово! Документ успешно создан.")
        print("=" * 60 + "\n")


def main():
    """Точка входа в приложение"""
    try:
        generator = PDFGenerator()
        generator.run()
    except KeyboardInterrupt:
        print("\n\n👋 Программа завершена пользователем")
    except Exception as e:
        print(f"\n✗ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()