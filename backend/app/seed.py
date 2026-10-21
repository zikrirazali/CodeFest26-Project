"""Bilingual demo data: one Python course, two lesson modules, five auto-graded challenges,
two squads with a realistic mix of contributors (including one who is coasting)."""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (Bounty, Challenge, Course, Enrollment, Module, Section, SectionProgress, Squad, SquadMember,
                     User, utcnow)
from .security import hash_password
from .services import ledger

DEMO_PASSWORD = "demo1234"

STUDENTS = [
    ("Amir Hakimi", "amir@student.tempa.my"),
    ("Tan Mei Ling", "meiling@student.tempa.my"),
    ("Ravi Kumar", "ravi@student.tempa.my"),
    ("Nurul Izzah", "nurul@student.tempa.my"),
    ("Daniel Wong", "daniel@student.tempa.my"),
    ("Siti Aminah", "siti@student.tempa.my"),
]

CHALLENGES = [
    dict(
        slug="sum-evens", skill_tag="python-basics", function_name="sum_evens",
        title_en="Sum of even numbers", title_ms="Jumlah nombor genap",
        prompt_en="Write `sum_evens(nums)` that returns the sum of all even integers in the list `nums`. "
                  "An empty list returns 0.",
        prompt_ms="Tulis `sum_evens(nums)` yang memulangkan jumlah semua integer genap dalam senarai `nums`. "
                  "Senarai kosong memulangkan 0.",
        starter_code="def sum_evens(nums):\n    # your code here\n    pass\n",
        tests=[
            {"args": [[1, 2, 3, 4]], "expected": 6},
            {"args": [[]], "expected": 0},
            {"args": [[-2, -3, 5]], "expected": -2, "hidden": True},
            {"args": [[0, 7, 10, 11]], "expected": 10, "hidden": True},
        ],
    ),
    dict(
        slug="palindrome", skill_tag="strings", function_name="is_palindrome",
        title_en="Clean palindrome check", title_ms="Semakan palindrom bersih",
        prompt_en="Write `is_palindrome(s)` that returns True if `s` reads the same backwards, "
                  "ignoring letter case and any character that is not a letter or digit.",
        prompt_ms="Tulis `is_palindrome(s)` yang memulangkan True jika `s` dibaca sama dari belakang, "
                  "dengan mengabaikan huruf besar/kecil dan sebarang aksara yang bukan huruf atau digit.",
        starter_code="def is_palindrome(s):\n    pass\n",
        tests=[
            {"args": ["Racecar"], "expected": True},
            {"args": ["hello"], "expected": False},
            {"args": ["A man, a plan, a canal: Panama!"], "expected": True, "hidden": True},
            {"args": [""], "expected": True, "hidden": True},
        ],
    ),
    dict(
        slug="word-count", skill_tag="data-structures", function_name="word_count",
        title_en="Word frequency counter", title_ms="Pengira kekerapan perkataan",
        prompt_en="Write `word_count(text)` that returns a dict mapping each lowercase word to how often it appears. "
                  "Words are separated by whitespace; strip the punctuation characters .,!? from each word.",
        prompt_ms="Tulis `word_count(text)` yang memulangkan dict yang memetakan setiap perkataan (huruf kecil) kepada "
                  "kekerapannya. Perkataan dipisahkan oleh ruang kosong; buang tanda baca .,!? daripada setiap perkataan.",
        starter_code="def word_count(text):\n    counts = {}\n    return counts\n",
        tests=[
            {"args": ["the cat the hat"], "expected": {"the": 2, "cat": 1, "hat": 1}},
            {"args": ["Saya suka, saya!"], "expected": {"saya": 2, "suka": 1}},
            {"args": [""], "expected": {}, "hidden": True},
            {"args": ["Go go GO?"], "expected": {"go": 3}, "hidden": True},
        ],
    ),
    dict(
        slug="moving-average", skill_tag="algorithms", function_name="moving_average",
        title_en="Moving average of grades", title_ms="Purata bergerak markah",
        prompt_en="Write `moving_average(nums, k)` returning the averages of every window of `k` consecutive numbers, "
                  "each rounded to 2 decimal places. If k is larger than the list, return [].",
        prompt_ms="Tulis `moving_average(nums, k)` yang memulangkan purata setiap tetingkap `k` nombor berturutan, "
                  "dibundarkan kepada 2 tempat perpuluhan. Jika k lebih besar daripada senarai, pulangkan [].",
        starter_code="def moving_average(nums, k):\n    pass\n",
        tests=[
            {"args": [[1, 2, 3, 4], 2], "expected": [1.5, 2.5, 3.5]},
            {"args": [[10, 20], 3], "expected": []},
            {"args": [[80, 75, 90], 3], "expected": [81.67], "hidden": True},
            {"args": [[5], 1], "expected": [5.0], "hidden": True},
        ],
    ),
    dict(
        slug="grade-letter", skill_tag="python-basics", function_name="grade_letter",
        title_en="Mark to grade", title_ms="Markah kepada gred",
        prompt_en="Write `grade_letter(mark)` returning 'A' for 80-100, 'B' for 65-79, 'C' for 50-64 and 'F' below 50. "
                  "Marks outside 0-100 return 'INVALID'.",
        prompt_ms="Tulis `grade_letter(mark)` yang memulangkan 'A' untuk 80-100, 'B' untuk 65-79, 'C' untuk 50-64 dan "
                  "'F' bawah 50. Markah di luar 0-100 memulangkan 'INVALID'.",
        starter_code="def grade_letter(mark):\n    pass\n",
        tests=[
            {"args": [85], "expected": "A"},
            {"args": [64], "expected": "C"},
            {"args": [80], "expected": "A", "hidden": True},
            {"args": [-5], "expected": "INVALID", "hidden": True},
            {"args": [101], "expected": "INVALID", "hidden": True},
        ],
    ),
]

MODULES = [
    {
        "title_en": "Lists and Loops", "title_ms": "Senarai dan Gelung",
        "sections": [
            dict(
                heading_en="What a list really is", heading_ms="Apakah sebenarnya senarai",
                body_en=(
                    "A Python list is an ordered, mutable collection. Ordered means every element has a position, "
                    "called an index, starting from zero: in marks = [72, 85, 60], marks[0] is 72 and marks[2] is 60. "
                    "Negative indexes count from the end, so marks[-1] is also 60.\n\n"
                    "Mutable means you can change a list after creating it. marks.append(91) adds to the end, "
                    "marks[1] = 88 replaces a value, and marks.pop() removes and returns the last element.\n\n"
                    "Lists can hold any type, even other lists, but a list of one kind of thing is far easier to reason "
                    "about. When you find yourself storing a name, an age and a mark together in one list, that is a "
                    "sign you want a dictionary or a small class instead."
                ),
                body_ms=(
                    "Senarai (list) Python ialah koleksi yang tertib dan boleh ubah. Tertib bermaksud setiap elemen "
                    "mempunyai kedudukan yang dipanggil indeks, bermula dari sifar: dalam marks = [72, 85, 60], "
                    "marks[0] ialah 72 dan marks[2] ialah 60. Indeks negatif dikira dari hujung, jadi marks[-1] juga 60.\n\n"
                    "Boleh ubah bermaksud anda boleh menukar senarai selepas ia dicipta. marks.append(91) menambah di "
                    "hujung, marks[1] = 88 menggantikan nilai, dan marks.pop() membuang serta memulangkan elemen terakhir.\n\n"
                    "Senarai boleh menyimpan apa-apa jenis data, malah senarai lain, tetapi senarai yang mengandungi satu "
                    "jenis data sahaja jauh lebih mudah difahami. Jika anda menyimpan nama, umur dan markah bersama dalam "
                    "satu senarai, itu petanda anda sepatutnya menggunakan dictionary atau kelas kecil."
                ),
                question_en="Given marks = [72, 85, 60], what is marks[-1]?",
                question_ms="Diberi marks = [72, 85, 60], apakah nilai marks[-1]?",
                options={"en": ["72", "85", "60", "An IndexError"], "ms": ["72", "85", "60", "IndexError"]},
                answer=2,
                explanation_en="Negative indexes count from the end: -1 is the last element.",
                explanation_ms="Indeks negatif dikira dari hujung: -1 ialah elemen terakhir.",
            ),
            dict(
                heading_en="Looping without losing track", heading_ms="Gelung tanpa hilang arah",
                body_en=(
                    "The for loop walks through a list one element at a time: for m in marks: print(m). You get the "
                    "values directly, which is almost always what you want.\n\n"
                    "When you also need the position, use enumerate: for i, m in enumerate(marks). Avoid "
                    "for i in range(len(marks)) unless you genuinely need to index into two lists at once; it is longer "
                    "and easier to get wrong.\n\n"
                    "A classic bug is changing a list while you loop over it. Removing items inside the loop shifts the "
                    "remaining elements left, so the loop silently skips some of them. Build a new list instead: "
                    "passed = [m for m in marks if m >= 50]. This is called a list comprehension and it reads almost "
                    "like English: the marks, for each mark in marks, if the mark is at least 50."
                ),
                body_ms=(
                    "Gelung for melalui senarai satu elemen pada satu masa: for m in marks: print(m). Anda terus "
                    "mendapat nilai, dan itulah yang hampir selalu anda perlukan.\n\n"
                    "Jika anda juga memerlukan kedudukan, gunakan enumerate: for i, m in enumerate(marks). Elakkan "
                    "for i in range(len(marks)) melainkan anda benar-benar perlu mengindeks dua senarai serentak; ia lebih "
                    "panjang dan lebih mudah tersilap.\n\n"
                    "Pepijat klasik ialah mengubah senarai semasa melaluinya dalam gelung. Membuang item di dalam gelung "
                    "menganjak elemen yang tinggal ke kiri, jadi gelung tersebut melangkau sebahagian daripadanya tanpa "
                    "amaran. Bina senarai baharu sebaliknya: passed = [m for m in marks if m >= 50]. Ini dipanggil list "
                    "comprehension dan ia dibaca hampir seperti ayat biasa."
                ),
                question_en="Why is removing items from a list while looping over it a bug?",
                question_ms="Mengapakah membuang item daripada senarai semasa gelung merupakan pepijat?",
                options={
                    "en": ["Python raises a SyntaxError", "Remaining items shift, so some are skipped",
                           "It makes the list immutable", "It is fine, there is no bug"],
                    "ms": ["Python menimbulkan SyntaxError", "Item yang tinggal teranjak, jadi ada yang dilangkau",
                           "Ia menjadikan senarai tidak boleh ubah", "Tiada masalah, tiada pepijat"],
                },
                answer=1,
                explanation_en="Each removal shifts later elements left while the loop index keeps moving forward.",
                explanation_ms="Setiap pembuangan menganjak elemen seterusnya ke kiri sedangkan indeks gelung terus bergerak ke depan.",
            ),
            dict(
                heading_en="Accumulators", heading_ms="Pengumpul (accumulator)",
                body_en=(
                    "Most loop problems are accumulator problems: start with an empty result, then update it once per "
                    "element. To total even marks you start with total = 0 and add each even value. To count words you "
                    "start with counts = {} and increase counts[word] each time.\n\n"
                    "Choose the starting value carefully, because it is also your answer for empty input. A sum starts "
                    "at 0, a product at 1, a list of results at [] and a running maximum at the first element, or "
                    "float('-inf') if the list might be empty.\n\n"
                    "Before you write the loop, say out loud what the accumulator means after each step, for example "
                    "'total is the sum of the even numbers seen so far'. If you can state that sentence, the code almost "
                    "writes itself, and you will catch edge cases such as negative numbers and zero."
                ),
                body_ms=(
                    "Kebanyakan masalah gelung ialah masalah pengumpul: mulakan dengan hasil kosong, kemudian kemas kini "
                    "sekali bagi setiap elemen. Untuk menjumlahkan markah genap, mulakan dengan total = 0 dan tambah setiap "
                    "nilai genap. Untuk mengira perkataan, mulakan dengan counts = {} dan tambah counts[word] setiap kali.\n\n"
                    "Pilih nilai permulaan dengan teliti kerana ia juga jawapan anda bagi input kosong. Jumlah bermula "
                    "pada 0, hasil darab pada 1, senarai hasil pada [] dan nilai maksimum pada elemen pertama, atau "
                    "float('-inf') jika senarai mungkin kosong.\n\n"
                    "Sebelum menulis gelung, nyatakan maksud pengumpul selepas setiap langkah, contohnya 'total ialah "
                    "jumlah nombor genap yang telah dilihat setakat ini'. Jika anda boleh menyatakan ayat itu, kod hampir "
                    "menulis dirinya sendiri, dan anda akan menangkap kes tepi seperti nombor negatif dan sifar."
                ),
                question_en="What should a running product start at?",
                question_ms="Apakah nilai permulaan bagi hasil darab berjalan?",
                options={"en": ["0", "1", "None", "The last element"], "ms": ["0", "1", "None", "Elemen terakhir"]},
                answer=1,
                explanation_en="1 is the identity for multiplication; starting at 0 makes every product 0.",
                explanation_ms="1 ialah identiti bagi pendaraban; bermula dengan 0 menjadikan semua hasil darab 0.",
            ),
        ],
    },
    {
        "title_en": "Functions and Testing", "title_ms": "Fungsi dan Pengujian",
        "sections": [
            dict(
                heading_en="Functions as contracts", heading_ms="Fungsi sebagai kontrak",
                body_en=(
                    "A function is a promise: given these inputs, I return this output. def grade_letter(mark) promises "
                    "a letter for a mark. The name, the parameters and the return value together form the contract.\n\n"
                    "Return values are not the same as printing. print shows text on the screen and gives back None; "
                    "return hands a value to whoever called the function so it can be used again. Automated graders, "
                    "including Tempa's referee, only see what you return.\n\n"
                    "Keep functions small and pure where you can: same inputs, same output, no hidden changes to the "
                    "outside world. Pure functions are easy to test, easy to reuse and easy for a teammate to trust."
                ),
                body_ms=(
                    "Fungsi ialah satu janji: diberi input ini, saya pulangkan output ini. def grade_letter(mark) "
                    "berjanji memulangkan gred bagi satu markah. Nama, parameter dan nilai pulangan bersama-sama "
                    "membentuk kontrak tersebut.\n\n"
                    "Nilai pulangan tidak sama dengan mencetak. print memaparkan teks di skrin dan memulangkan None; "
                    "return menyerahkan nilai kepada pemanggil fungsi supaya ia boleh digunakan semula. Penggred "
                    "automatik, termasuk referee Tempa, hanya melihat apa yang anda pulangkan.\n\n"
                    "Pastikan fungsi kecil dan tulen jika boleh: input yang sama, output yang sama, tiada perubahan "
                    "tersembunyi kepada dunia luar. Fungsi tulen mudah diuji, mudah diguna semula dan mudah dipercayai "
                    "oleh rakan sepasukan."
                ),
                question_en="A function prints the answer but has no return statement. What does the caller receive?",
                question_ms="Sebuah fungsi mencetak jawapan tetapi tiada pernyataan return. Apakah yang diterima pemanggil?",
                options={"en": ["The printed text", "None", "0", "An error"],
                         "ms": ["Teks yang dicetak", "None", "0", "Ralat"]},
                answer=1,
                explanation_en="Without return, a Python function returns None.",
                explanation_ms="Tanpa return, fungsi Python memulangkan None.",
            ),
            dict(
                heading_en="Edge cases win marks", heading_ms="Kes tepi menentukan markah",
                body_en=(
                    "Most bugs live at the edges: empty input, a single element, zero, negative numbers, boundaries such "
                    "as exactly 80 when A starts at 80, and unexpected capital letters or punctuation.\n\n"
                    "Hidden tests on the Bounty Board target exactly these. Passing the visible examples only proves you "
                    "handle the typical case. Before submitting, list three inputs that might break your function and "
                    "trace them by hand.\n\n"
                    "Boundary conditions deserve special care with comparison operators. If A is 80 to 100, the test is "
                    "mark >= 80, not mark > 80. Off-by-one errors are the single most common reason a correct-looking "
                    "solution fails."
                ),
                body_ms=(
                    "Kebanyakan pepijat berada di tepi: input kosong, satu elemen, sifar, nombor negatif, sempadan seperti "
                    "tepat 80 apabila A bermula pada 80, serta huruf besar atau tanda baca yang tidak dijangka.\n\n"
                    "Ujian tersembunyi di Papan Ganjaran menyasarkan kes-kes ini. Lulus contoh yang kelihatan hanya "
                    "membuktikan anda mengendalikan kes biasa. Sebelum menghantar, senaraikan tiga input yang mungkin "
                    "merosakkan fungsi anda dan surih secara manual.\n\n"
                    "Syarat sempadan memerlukan perhatian khusus terhadap operator perbandingan. Jika A ialah 80 hingga "
                    "100, ujiannya ialah mark >= 80, bukan mark > 80. Ralat off-by-one ialah sebab paling biasa penyelesaian "
                    "yang kelihatan betul gagal."
                ),
                question_en="A is 80-100. Which condition is correct?",
                question_ms="A ialah 80-100. Syarat manakah yang betul?",
                options={"en": ["mark > 80", "mark >= 80 and mark <= 100", "mark == 80", "mark < 100"],
                         "ms": ["mark > 80", "mark >= 80 and mark <= 100", "mark == 80", "mark < 100"]},
                answer=1,
                explanation_en="Both boundaries, 80 and 100, are inclusive.",
                explanation_ms="Kedua-dua sempadan, 80 dan 100, adalah inklusif.",
            ),
            dict(
                heading_en="Testing like a referee", heading_ms="Menguji seperti referee",
                body_en=(
                    "A test is just code that calls your function and checks the result: assert grade_letter(85) == 'A'. "
                    "If the assertion is false, Python raises an AssertionError and tells you which line failed.\n\n"
                    "Write one test per idea: one for the typical case, one for each boundary and one for invalid input. "
                    "Name what each test proves. When a test fails, the name should tell you what broke without reading "
                    "the code.\n\n"
                    "Tempa's referee does the same thing at scale. It runs your function in an isolated process against "
                    "visible and hidden tests, so the result does not depend on who submitted it or how confident they "
                    "sounded in the group chat. Verified work is the only work that earns points."
                ),
                body_ms=(
                    "Ujian hanyalah kod yang memanggil fungsi anda dan menyemak hasilnya: assert grade_letter(85) == 'A'. "
                    "Jika penegasan itu palsu, Python menimbulkan AssertionError dan memberitahu baris mana yang gagal.\n\n"
                    "Tulis satu ujian bagi setiap idea: satu untuk kes biasa, satu untuk setiap sempadan dan satu untuk "
                    "input tidak sah. Namakan apa yang dibuktikan oleh setiap ujian. Apabila ujian gagal, namanya patut "
                    "memberitahu apa yang rosak tanpa perlu membaca kod.\n\n"
                    "Referee Tempa melakukan perkara yang sama secara berskala. Ia menjalankan fungsi anda dalam proses "
                    "terasing terhadap ujian yang kelihatan dan tersembunyi, jadi keputusannya tidak bergantung pada siapa "
                    "yang menghantar atau betapa yakinnya mereka dalam kumpulan sembang. Hanya kerja yang disahkan "
                    "memperoleh mata."
                ),
                question_en="What happens when `assert grade_letter(85) == 'A'` is false?",
                question_ms="Apakah yang berlaku apabila `assert grade_letter(85) == 'A'` adalah palsu?",
                options={"en": ["Nothing", "It prints False", "An AssertionError is raised", "The function is retried"],
                         "ms": ["Tiada apa-apa", "Ia mencetak False", "AssertionError ditimbulkan", "Fungsi dicuba semula"]},
                answer=2,
                explanation_en="A failing assert raises AssertionError.",
                explanation_ms="assert yang gagal menimbulkan AssertionError.",
            ),
        ],
    },
]

SQUAD_BOUNTIES = [
    # (challenge slug or None, points, skill, kind, title_en, title_ms, desc_en, desc_ms)
    ("grade-letter", 15, "python-basics", "code", "Grade conversion function", "Fungsi penukaran gred",
     "Core rule used by the whole analyzer.", "Peraturan teras yang digunakan oleh keseluruhan penganalisis."),
    ("moving-average", 25, "algorithms", "code", "Trend line: moving average", "Garis trend: purata bergerak",
     "Smooths each student's marks across assessments.", "Melicinkan markah setiap pelajar merentas penilaian."),
    ("sum-evens", 10, "python-basics", "code", "Warm-up utility: sum of evens", "Utiliti pemanasan: jumlah genap",
     "Small helper used by the stats module.", "Fungsi pembantu kecil untuk modul statistik."),
    ("word-count", 20, "data-structures", "code", "Feedback keyword counter", "Pengira kata kunci maklum balas",
     "Counts keywords in lecturer feedback comments.", "Mengira kata kunci dalam komen maklum balas pensyarah."),
    ("palindrome", 15, "strings", "code", "Input sanitiser check", "Semakan pembersih input",
     "String cleaning used before matching student IDs.", "Pembersihan rentetan sebelum memadankan ID pelajar."),
    (None, 20, "system-design", "artifact", "UML class diagram", "Rajah kelas UML",
     "Paste a link to (or PlantUML for) the class diagram: Student, Assessment, Report.",
     "Tampal pautan kepada (atau kod PlantUML untuk) rajah kelas: Student, Assessment, Report."),
    (None, 15, "communication", "artifact", "README and user guide (BM + EN)", "README dan panduan pengguna (BM + EN)",
     "Bilingual README explaining how to run and use the analyzer.",
     "README dwibahasa yang menerangkan cara menjalankan dan menggunakan penganalisis."),
]

SOLUTIONS = {
    "grade-letter": "def grade_letter(mark):\n    if mark < 0 or mark > 100:\n        return 'INVALID'\n"
                    "    if mark >= 80:\n        return 'A'\n    if mark >= 65:\n        return 'B'\n"
                    "    if mark >= 50:\n        return 'C'\n    return 'F'\n",
    "moving-average": "def moving_average(nums, k):\n    return [round(sum(nums[i:i+k])/k, 2) "
                      "for i in range(len(nums)-k+1)] if k <= len(nums) else []\n",
    "sum-evens": "def sum_evens(nums):\n    return sum(n for n in nums if n % 2 == 0)\n",
}


def seed(db: Session) -> None:
    if db.scalar(select(User).limit(1)) is not None:
        return
    pw = hash_password(DEMO_PASSWORD)
    lecturer = User(name="Dr. Aisyah Rahman", email="lecturer@tempa.my", password_hash=pw, role="lecturer")
    students = [User(name=n, email=e, password_hash=pw) for n, e in STUDENTS]
    db.add_all([lecturer, *students])
    db.flush()

    course = Course(code="CSC1024", title_en="Python Programming Fundamentals",
                    title_ms="Asas Pengaturcaraan Python", lecturer_id=lecturer.id)
    db.add(course)
    db.flush()
    db.add_all([Enrollment(course_id=course.id, user_id=s.id) for s in students])

    challenges = {c["slug"]: Challenge(**c) for c in CHALLENGES}
    db.add_all(challenges.values())

    sections = []
    for pos, m in enumerate(MODULES, start=1):
        module = Module(course_id=course.id, position=pos, title_en=m["title_en"], title_ms=m["title_ms"])
        db.add(module)
        db.flush()
        for spos, s in enumerate(m["sections"], start=1):
            sec = Section(module_id=module.id, position=spos, **s)
            db.add(sec)
            sections.append(sec)
    db.flush()

    squads = [
        Squad(course_id=course.id, name="Squad Alpha", project_en="Student Grade Analyzer",
              project_ms="Penganalisis Gred Pelajar"),
        Squad(course_id=course.id, name="Squad Beta", project_en="Student Grade Analyzer",
              project_ms="Penganalisis Gred Pelajar"),
    ]
    squads[0].members = [SquadMember(user_id=s.id) for s in students[:3]]
    squads[1].members = [SquadMember(user_id=s.id) for s in students[3:]]
    db.add_all(squads)
    db.flush()

    for squad in squads:
        for slug, pts, skill, kind, ten, tms, den, dms in SQUAD_BOUNTIES:
            db.add(Bounty(squad_id=squad.id, title_en=ten, title_ms=tms, description_en=den, description_ms=dms,
                          points=pts, skill_tag=skill, kind=kind,
                          challenge_id=challenges[slug].id if slug else None))
    db.flush()

    # History: in Squad Alpha, Amir and Mei Ling deliver while Ravi coasts.
    now = utcnow()
    amir, meiling, ravi, nurul, daniel, siti = students
    history = [
        (squads[0], "Grade conversion function", amir, 3),
        (squads[0], "Trend line: moving average", amir, 2),
        (squads[0], "Warm-up utility: sum of evens", meiling, 1),
        (squads[1], "Grade conversion function", nurul, 2),
        (squads[1], "Warm-up utility: sum of evens", daniel, 1),
        (squads[1], "Trend line: moving average", siti, 0),
    ]
    for squad, title, student, days_ago in history:
        b = db.scalar(select(Bounty).where(Bounty.squad_id == squad.id, Bounty.title_en == title))
        at = now - timedelta(days=days_ago, hours=2)
        b.status, b.claimed_by_id, b.claimed_at, b.verified_at = "verified", student.id, at - timedelta(hours=5), at
        ledger.append(db, student, "bounty", b.points, b.skill_tag, f"bounty:{b.id}", note=b.title_en, created_at=at)

    # Reading history so pace profiles and the lecturer dashboard have signal.
    for student, n_read, rushes, days_ago in [(amir, 3, 0, 3), (meiling, 2, 1, 2), (nurul, 3, 0, 1), (ravi, 1, 2, 4)]:
        for i, sec in enumerate(sections[:n_read]):
            at = now - timedelta(days=days_ago - min(i, days_ago), hours=1)
            method = "checkpoint" if rushes and i == 0 else "read"
            db.add(SectionProgress(user_id=student.id, section_id=sec.id, served_at=at - timedelta(minutes=3),
                                   unlocked_at=at, method=method, rush_count=rushes if i == 0 else 0,
                                   attempts=1 if method == "checkpoint" else 0,
                                   first_try_correct=True if method == "checkpoint" else None))
            ledger.append(db, student, "checkpoint" if method == "checkpoint" else "section_read",
                          3 if method == "checkpoint" else 2, "reading", f"section:{sec.id}",
                          note=sec.heading_en, created_at=at)

    # Mei Ling has an artifact waiting for lecturer review.
    uml = db.scalar(select(Bounty).where(Bounty.squad_id == squads[0].id, Bounty.title_en == "UML class diagram"))
    uml.status, uml.claimed_by_id, uml.claimed_at = "submitted", meiling.id, now - timedelta(hours=6)
    from .models import Submission
    db.add(Submission(bounty_id=uml.id, user_id=meiling.id, verdict="pending_review",
                      content="@startuml\nclass Student {\n  +id: str\n  +name: str\n}\nclass Assessment {\n"
                              "  +title: str\n  +weight: float\n}\nclass Report {\n  +generate(): str\n}\n"
                              "Student \"1\" -- \"*\" Assessment\nReport ..> Student\n@enduml"))
    db.commit()
