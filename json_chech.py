import sqlite3
import json


def dump_favorites_to_json():
    conn = sqlite3.connect("favorites.db")
    cursor = conn.cursor()

    cursor.execute('SELECT user_id, "group" FROM favorites')
    rows = cursor.fetchall()
    conn.close()

    favorites_list = [{"user_id": row[0], "group": row[1]} for row in rows]
    json_output = json.dumps(favorites_list, ensure_ascii=False, indent=2)

    print(json_output)  # Выводим в консоль

    # Если хочешь сохранить в файл:
    # with open("favorites.json", "w", encoding="utf-8") as f:
    #     f.write(json_output)


if __name__ == "__main__":
    dump_favorites_to_json()
