#ifndef UNICODE
#define UNICODE
#endif

#ifndef _UNICODE
#define _UNICODE
#endif

#include <windows.h>
#include <commdlg.h>
#include <commctrl.h>
#include <shellapi.h>

#include "resource.h"

#include <algorithm>
#include <cwctype>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#pragma comment(lib, "comdlg32.lib")
#pragma comment(lib, "comctl32.lib")
#pragma comment(lib, "shell32.lib")

namespace {

constexpr int kAppWidth = 1120;
constexpr int kAppHeight = 740;
constexpr const wchar_t* kAppVersion = L"Auto Adder 0.2";

constexpr int IDC_DOC_LIST = 1001;
constexpr int IDC_ADD_DOCS = 1002;
constexpr int IDC_REMOVE_DOC = 1003;
constexpr int IDC_CLEAR_DOCS = 1004;
constexpr int IDC_SAMPLE_PATH = 1005;
constexpr int IDC_PICK_SAMPLE = 1006;
constexpr int IDC_SAMPLE_KIND = 1007;
constexpr int IDC_FIELD_LIST = 1008;
constexpr int IDC_EXTRACT = 1009;
constexpr int IDC_FILL = 1010;
constexpr int IDC_LOG = 1011;
constexpr int IDC_STATUS = 1012;

struct FieldValue {
    std::wstring name;
    std::wstring value;
};

struct AppState {
    std::vector<std::wstring> documents;
    std::wstring samplePath;
    std::vector<FieldValue> fields;
};

AppState g_state;
HWND g_mainWindow = nullptr;
HWND g_docList = nullptr;
HWND g_samplePath = nullptr;
HWND g_sampleKind = nullptr;
HWND g_fieldList = nullptr;
HWND g_log = nullptr;
HWND g_status = nullptr;

std::string WideToUtf8(const std::wstring& text) {
    if (text.empty()) {
        return {};
    }

    const int size = WideCharToMultiByte(CP_UTF8, 0, text.c_str(), -1, nullptr, 0, nullptr, nullptr);
    if (size <= 0) {
        return {};
    }

    std::string result(static_cast<size_t>(size - 1), '\0');
    WideCharToMultiByte(CP_UTF8, 0, text.c_str(), -1, result.data(), size, nullptr, nullptr);
    return result;
}

std::wstring Utf8ToWide(const std::string& text) {
    if (text.empty()) {
        return {};
    }

    const int size = MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, nullptr, 0);
    if (size <= 0) {
        return {};
    }

    std::wstring result(static_cast<size_t>(size - 1), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, result.data(), size);
    return result;
}

std::wstring JsonEscape(const std::wstring& text) {
    std::wstring escaped;
    escaped.reserve(text.size() + 8);
    for (wchar_t ch : text) {
        switch (ch) {
        case L'\\':
            escaped += L"\\\\";
            break;
        case L'"':
            escaped += L"\\\"";
            break;
        case L'\n':
            escaped += L"\\n";
            break;
        case L'\r':
            escaped += L"\\r";
            break;
        case L'\t':
            escaped += L"\\t";
            break;
        default:
            escaped += ch;
            break;
        }
    }
    return escaped;
}

std::wstring GetExeDirectory() {
    wchar_t buffer[MAX_PATH]{};
    GetModuleFileNameW(nullptr, buffer, MAX_PATH);
    return std::filesystem::path(buffer).parent_path().wstring();
}

std::wstring FindEngineScript() {
    const std::wstring exeDir = GetExeDirectory();
    const std::vector<std::filesystem::path> candidates = {
        std::filesystem::path(exeDir) / L".." / L".." / L"engine" / L"auto_adder_engine.py",
        std::filesystem::path(exeDir) / L".." / L"engine" / L"auto_adder_engine.py",
        std::filesystem::path(exeDir) / L"engine" / L"auto_adder_engine.py",
    };

    for (const auto& candidate : candidates) {
        std::error_code error;
        const auto resolved = std::filesystem::weakly_canonical(candidate, error);
        if (!error && std::filesystem::exists(resolved)) {
            return resolved.wstring();
        }
    }

    return L"";
}

std::wstring FindPythonLauncher() {
    wchar_t buffer[MAX_PATH]{};
    const std::wstring exeDir = GetExeDirectory();
    const std::vector<std::filesystem::path> localCandidates = {
        std::filesystem::path(exeDir) / L".." / L".." / L".venv" / L"Scripts" / L"python.exe",
        std::filesystem::path(exeDir) / L".." / L".venv" / L"Scripts" / L"python.exe",
        std::filesystem::path(exeDir) / L".venv" / L"Scripts" / L"python.exe",
        std::filesystem::path(exeDir) / L"python" / L"python.exe",
    };

    for (const auto& candidate : localCandidates) {
        std::error_code error;
        const auto resolved = std::filesystem::weakly_canonical(candidate, error);
        if (!error && std::filesystem::exists(resolved)) {
            return std::wstring(L"\"") + resolved.wstring() + L"\"";
        }
    }

    if (SearchPathW(nullptr, L"py.exe", nullptr, MAX_PATH, buffer, nullptr)) {
        return std::wstring(L"\"") + buffer + L"\" -3";
    }
    if (SearchPathW(nullptr, L"python.exe", nullptr, MAX_PATH, buffer, nullptr)) {
        return std::wstring(L"\"") + buffer + L"\"";
    }
    if (SearchPathW(nullptr, L"python3.exe", nullptr, MAX_PATH, buffer, nullptr)) {
        return std::wstring(L"\"") + buffer + L"\"";
    }

    return L"";
}

bool WriteUtf8File(const std::wstring& path, const std::string& content) {
    std::ofstream stream(std::filesystem::path(path), std::ios::binary);
    if (!stream) {
        return false;
    }
    stream.write(content.data(), static_cast<std::streamsize>(content.size()));
    return static_cast<bool>(stream);
}

std::wstring QuoteArgument(const std::wstring& text) {
    return L"\"" + text + L"\"";
}

bool RunProcessCaptureOutput(const std::wstring& commandLine, std::string& output) {
    SECURITY_ATTRIBUTES securityAttributes{};
    securityAttributes.nLength = sizeof(securityAttributes);
    securityAttributes.bInheritHandle = TRUE;

    HANDLE readPipe = nullptr;
    HANDLE writePipe = nullptr;
    if (!CreatePipe(&readPipe, &writePipe, &securityAttributes, 0)) {
        return false;
    }

    SetHandleInformation(readPipe, HANDLE_FLAG_INHERIT, 0);

    STARTUPINFOW startupInfo{};
    startupInfo.cb = sizeof(startupInfo);
    startupInfo.dwFlags = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
    startupInfo.hStdOutput = writePipe;
    startupInfo.hStdError = writePipe;
    startupInfo.wShowWindow = SW_HIDE;

    PROCESS_INFORMATION processInfo{};
    std::vector<wchar_t> mutableCommandLine(commandLine.begin(), commandLine.end());
    mutableCommandLine.push_back(L'\0');

    const BOOL created = CreateProcessW(
        nullptr,
        mutableCommandLine.data(),
        nullptr,
        nullptr,
        TRUE,
        CREATE_NO_WINDOW,
        nullptr,
        nullptr,
        &startupInfo,
        &processInfo
    );

    CloseHandle(writePipe);

    if (!created) {
        CloseHandle(readPipe);
        return false;
    }

    char buffer[4096]{};
    DWORD bytesRead = 0;
    while (ReadFile(readPipe, buffer, sizeof(buffer), &bytesRead, nullptr) && bytesRead > 0) {
        output.append(buffer, buffer + bytesRead);
    }

    WaitForSingleObject(processInfo.hProcess, INFINITE);
    CloseHandle(processInfo.hThread);
    CloseHandle(processInfo.hProcess);
    CloseHandle(readPipe);
    return true;
}

std::wstring ExtractJsonString(const std::string& json, const std::string& key, size_t startPos = 0) {
    const std::string marker = "\"" + key + "\":\"";
    const size_t pos = json.find(marker, startPos);
    if (pos == std::string::npos) {
        return L"";
    }

    size_t cursor = pos + marker.size();
    std::string raw;
    while (cursor < json.size()) {
        const char ch = json[cursor++];
        if (ch == '\\' && cursor < json.size()) {
            const char next = json[cursor++];
            if (next == 'n') {
                raw.push_back('\n');
            } else if (next == 'r') {
                raw.push_back('\r');
            } else if (next == 't') {
                raw.push_back('\t');
            } else {
                raw.push_back(next);
            }
            continue;
        }
        if (ch == '"') {
            break;
        }
        raw.push_back(ch);
    }

    return Utf8ToWide(raw);
}

std::vector<FieldValue> ParseFieldsFromJson(const std::string& json) {
    std::vector<FieldValue> fields;
    size_t searchPos = 0;

    while (true) {
        const size_t namePos = json.find("\"name\":\"", searchPos);
        if (namePos == std::string::npos) {
            break;
        }

        const std::wstring name = ExtractJsonString(json, "name", namePos);
        const std::wstring value = ExtractJsonString(json, "value", namePos);
        if (!name.empty()) {
            fields.push_back({name, value});
        }

        searchPos = namePos + 8;
    }

    return fields;
}

bool EngineExtractFields(const std::wstring& samplePath, const std::wstring& sampleKind, std::vector<FieldValue>& fields, std::wstring& errorText) {
    const std::wstring python = FindPythonLauncher();
    const std::wstring engine = FindEngineScript();
    if (python.empty()) {
        errorText = L"Python не найден. Установите Python 3 и зависимости: pip install -r requirements.txt";
        return false;
    }
    if (engine.empty()) {
        errorText = L"Не найден engine/auto_adder_engine.py рядом с приложением.";
        return false;
    }

    std::wstring command = FindPythonLauncher() + L" " + QuoteArgument(engine)
        + L" extract --sample " + QuoteArgument(samplePath)
        + L" --kind " + QuoteArgument(sampleKind);

    std::string output;
    if (!RunProcessCaptureOutput(command, output)) {
        errorText = L"Не удалось запустить локальный модуль извлечения.";
        return false;
    }

    if (output.find("\"ok\": false") != std::string::npos || output.find("\"ok\":false") != std::string::npos) {
        errorText = ExtractJsonString(output, "error");
        if (errorText.empty()) {
            errorText = L"Модуль извлечения вернул ошибку.";
        }
        return false;
    }

    fields = ParseFieldsFromJson(output);
    if (fields.empty()) {
        errorText = L"Данные не извлечены. Проверьте качество скана или заполните поля вручную.";
        return false;
    }

    return true;
}

bool EngineFillDocuments(const std::vector<std::wstring>& documents, const std::vector<FieldValue>& fields, std::wstring& summary, std::wstring& errorText) {
    const std::wstring python = FindPythonLauncher();
    const std::wstring engine = FindEngineScript();
    if (python.empty() || engine.empty()) {
        errorText = L"Python или engine/auto_adder_engine.py не найдены.";
        return false;
    }

    const std::wstring tempDir = std::filesystem::temp_directory_path().wstring();
    const std::wstring documentsFile = tempDir + L"\\auto_adder_documents.json";
    const std::wstring fieldsFile = tempDir + L"\\auto_adder_fields.json";

    std::string documentsJson = "[";
    for (size_t i = 0; i < documents.size(); ++i) {
        if (i > 0) {
            documentsJson += ",";
        }
        documentsJson += "\"" + WideToUtf8(JsonEscape(documents[i])) + "\"";
    }
    documentsJson += "]";

    std::string fieldsJson = "[";
    for (size_t i = 0; i < fields.size(); ++i) {
        if (i > 0) {
            fieldsJson += ",";
        }
        fieldsJson += "{\"name\":\"" + WideToUtf8(JsonEscape(fields[i].name))
            + "\",\"value\":\"" + WideToUtf8(JsonEscape(fields[i].value)) + "\"}";
    }
    fieldsJson += "]";

    if (!WriteUtf8File(documentsFile, documentsJson) || !WriteUtf8File(fieldsFile, fieldsJson)) {
        errorText = L"Не удалось подготовить временные файлы для заполнения.";
        return false;
    }

    std::wstring command = FindPythonLauncher() + L" " + QuoteArgument(engine)
        + L" fill --documents-file " + QuoteArgument(documentsFile)
        + L" --fields-file " + QuoteArgument(fieldsFile);

    std::string output;
    if (!RunProcessCaptureOutput(command, output)) {
        errorText = L"Не удалось запустить модуль заполнения документов.";
        return false;
    }

    if (output.find("\"ok\": false") != std::string::npos || output.find("\"ok\":false") != std::string::npos) {
        errorText = ExtractJsonString(output, "error");
        if (errorText.empty()) {
            errorText = L"Модуль заполнения вернул ошибку.";
        }
        return false;
    }

    const size_t filledPos = output.find("\"filled\":");
    if (filledPos != std::string::npos) {
        const size_t digits = output.find_first_of("0123456789", filledPos);
        if (digits != std::string::npos) {
            summary = L"Заполнено документов: " + Utf8ToWide(output.substr(digits, output.find_first_not_of("0123456789", digits) - digits));
        }
    }

    size_t searchPos = 0;
    while (true) {
        const size_t pathPos = output.find("\"path\":\"", searchPos);
        if (pathPos == std::string::npos) {
            break;
        }

        const std::wstring path = ExtractJsonString(output, "path", pathPos);
        const size_t okPos = output.find("\"ok\": true", pathPos);
        const size_t okPosCompact = output.find("\"ok\":true", pathPos);
        const bool ok = (okPos != std::string::npos && okPos < pathPos + 200) ||
                        (okPosCompact != std::string::npos && okPosCompact < pathPos + 200);

        if (!path.empty()) {
            summary += ok ? L"\n✓ " : L"\n✗ ";
            summary += path;
            if (!ok) {
                const std::wstring itemError = ExtractJsonString(output, "error", pathPos);
                if (!itemError.empty()) {
                    summary += L" — " + itemError;
                }
            }
        }

        searchPos = pathPos + 8;
    }

    return !summary.empty();
}

void ReadFieldsFromListView() {
    for (int i = 0; i < static_cast<int>(g_state.fields.size()); ++i) {
        wchar_t value[512]{};
        ListView_GetItemText(g_fieldList, i, 1, value, 511);
        g_state.fields[i].value = value;
    }
}

bool EditSelectedFieldValue(HWND owner) {
    const int selected = ListView_GetNextItem(g_fieldList, -1, LVNI_SELECTED);
    if (selected < 0 || selected >= static_cast<int>(g_state.fields.size())) {
        return false;
    }

    RECT cellRect{};
    ListView_GetSubItemRect(g_fieldList, selected, 1, LVIR_BOUNDS, &cellRect);
    MapWindowPoints(g_fieldList, owner, reinterpret_cast<POINT*>(&cellRect), 2);

    std::wstring edited = g_state.fields[selected].value;
    HWND editor = CreateWindowExW(
        WS_EX_CLIENTEDGE,
        L"EDIT",
        edited.c_str(),
        WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL,
        cellRect.left,
        cellRect.top,
        cellRect.right - cellRect.left,
        cellRect.bottom - cellRect.top,
        owner,
        nullptr,
        GetModuleHandleW(nullptr),
        nullptr
    );

    if (!editor) {
        return false;
    }

    SendMessageW(editor, WM_SETFONT, SendMessageW(g_fieldList, WM_GETFONT, 0, 0), TRUE);
    SetFocus(editor);
    SendMessageW(editor, EM_SETSEL, 0, -1);

    bool accepted = false;
    MSG message{};
    while (IsWindow(editor)) {
        if (!GetMessageW(&message, nullptr, 0, 0)) {
            break;
        }

        if (message.message == WM_KEYDOWN && message.hwnd == editor) {
            if (message.wParam == VK_RETURN) {
                wchar_t buffer[512]{};
                GetWindowTextW(editor, buffer, 511);
                edited = buffer;
                accepted = true;
                DestroyWindow(editor);
                break;
            }
            if (message.wParam == VK_ESCAPE) {
                DestroyWindow(editor);
                return false;
            }
        }

        if (message.message == WM_LBUTTONDOWN && message.hwnd != editor) {
            wchar_t buffer[512]{};
            GetWindowTextW(editor, buffer, 511);
            edited = buffer;
            accepted = true;
            DestroyWindow(editor);
            break;
        }

        TranslateMessage(&message);
        DispatchMessageW(&message);
    }

    if (!accepted) {
        return false;
    }

    g_state.fields[selected].value = edited;
    ListView_SetItemText(g_fieldList, selected, 1, const_cast<wchar_t*>(edited.c_str()));
    return true;
}

std::wstring JoinPathListFromDialogBuffer(const wchar_t* buffer) {
    return buffer ? std::wstring(buffer) : std::wstring();
}

std::wstring FileNameOnly(const std::wstring& path) {
    std::filesystem::path filePath(path);
    return filePath.filename().wstring();
}

std::wstring StemOnly(const std::wstring& path) {
    std::filesystem::path filePath(path);
    return filePath.stem().wstring();
}

std::wstring ExtensionLower(const std::wstring& path) {
    std::filesystem::path filePath(path);
    std::wstring extension = filePath.extension().wstring();
    std::transform(extension.begin(), extension.end(), extension.begin(), towlower);
    return extension;
}

std::wstring ToLower(std::wstring text) {
    std::transform(text.begin(), text.end(), text.begin(), towlower);
    return text;
}

bool ContainsInsensitive(const std::wstring& text, const std::wstring& needle) {
    return ToLower(text).find(ToLower(needle)) != std::wstring::npos;
}

std::wstring Trim(const std::wstring& text) {
    const auto first = std::find_if_not(text.begin(), text.end(), iswspace);
    if (first == text.end()) {
        return L"";
    }

    const auto last = std::find_if_not(text.rbegin(), text.rend(), iswspace).base();
    return std::wstring(first, last);
}

bool IsDigitsOnly(const std::wstring& text) {
    return !text.empty() && std::all_of(text.begin(), text.end(), iswdigit);
}

std::wstring FindFirstIinLikeNumber(const std::wstring& text) {
    std::wstring current;
    for (wchar_t ch : text) {
        if (iswdigit(ch)) {
            current.push_back(ch);
            if (current.size() == 12) {
                return current;
            }
        } else {
            current.clear();
        }
    }

    return L"";
}

std::vector<std::wstring> SplitWords(std::wstring text) {
    for (wchar_t& ch : text) {
        if (ch == L'_' || ch == L'-' || ch == L'.' || ch == L',' || ch == L'(' || ch == L')') {
            ch = L' ';
        }
    }

    std::wstringstream stream(text);
    std::vector<std::wstring> words;
    std::wstring word;
    while (stream >> word) {
        words.push_back(word);
    }
    return words;
}

bool IsNoiseWord(const std::wstring& word) {
    const std::wstring lower = ToLower(word);
    return lower == L"договор" || lower == L"материальной" || lower == L"ответственности" ||
           lower == L"заявление" || lower == L"предоставление" || lower == L"вычетов" ||
           lower == L"ипн" || lower == L"работника" || lower == L"образец" ||
           lower == L"на" || lower == L"о" || lower == L"и" || IsDigitsOnly(lower);
}

std::wstring GuessPersonNameFromFile(const std::wstring& path) {
    std::vector<std::wstring> usefulWords;
    for (const auto& word : SplitWords(StemOnly(path))) {
        if (!IsNoiseWord(word)) {
            usefulWords.push_back(word);
        }
    }

    if (usefulWords.size() < 2) {
        return L"";
    }

    std::wstringstream result;
    const size_t start = usefulWords.size() > 3 ? usefulWords.size() - 3 : 0;
    for (size_t i = start; i < usefulWords.size(); ++i) {
        if (i > start) {
            result << L' ';
        }
        result << usefulWords[i];
    }
    return result.str();
}

std::wstring CurrentDateText() {
    SYSTEMTIME time{};
    GetLocalTime(&time);

    wchar_t buffer[16]{};
    wsprintfW(buffer, L"%02d.%02d.%04d", time.wDay, time.wMonth, time.wYear);
    return buffer;
}

bool IsSupportedTargetDocument(const std::wstring& path) {
    const std::wstring ext = ExtensionLower(path);
    return ext == L".docx" || ext == L".pptx" || ext == L".xlsx";
}

bool IsSupportedSample(const std::wstring& path) {
    const std::wstring ext = ExtensionLower(path);
    return ext == L".jpg" || ext == L".jpeg" || ext == L".png" ||
           ext == L".bmp" || ext == L".pdf" || ext == L".txt" ||
           ext == L".csv" || ext == L".docx" || ext == L".doc" ||
           ext == L".xlsx" || ext == L".xls";
}

std::wstring DocumentProfile(const std::wstring& path) {
    const std::wstring name = FileNameOnly(path);
    const std::wstring ext = ExtensionLower(path);

    if (ContainsInsensitive(name, L"договор") || ContainsInsensitive(name, L"материаль")) {
        return L"договор";
    }
    if (ContainsInsensitive(name, L"ипн") || ContainsInsensitive(name, L"вычет")) {
        return L"заявление ИПН";
    }
    if (ext == L".xlsx" || ext == L".xls") {
        return L"Excel-форма";
    }
    if (ext == L".docx" || ext == L".doc") {
        return L"Word-шаблон";
    }
    if (ext == L".pdf") {
        return L"PDF";
    }
    if (ext == L".pptx" || ext == L".ppt") {
        return L"PowerPoint";
    }

    return L"документ";
}

std::wstring GuessSampleKind(const std::wstring& path) {
    const std::wstring name = FileNameOnly(path);
    const std::wstring ext = ExtensionLower(path);

    if (ContainsInsensitive(name, L"материаль") || ContainsInsensitive(name, L"ответствен")) {
        return L"Договор материальной ответственности";
    }
    if (ContainsInsensitive(name, L"ипн") || ContainsInsensitive(name, L"вычет")) {
        return L"Заявление на вычеты ИПН";
    }
    if (FindFirstIinLikeNumber(name).size() == 12 || ext == L".jpg" || ext == L".jpeg" || ext == L".png" || ext == L".bmp") {
        return L"Удостоверение личности";
    }
    if (ContainsInsensitive(name, L"паспорт")) {
        return L"Паспорт";
    }

    return L"Комплект кадровых документов";
}

void SelectComboText(HWND combo, const std::wstring& text) {
    const int count = static_cast<int>(SendMessageW(combo, CB_GETCOUNT, 0, 0));
    for (int i = 0; i < count; ++i) {
        wchar_t item[160]{};
        SendMessageW(combo, CB_GETLBTEXT, i, reinterpret_cast<LPARAM>(item));
        if (text == item) {
            SendMessageW(combo, CB_SETCURSEL, i, 0);
            return;
        }
    }
}

void AppendLog(const std::wstring& text) {
    const int length = GetWindowTextLengthW(g_log);
    SendMessageW(g_log, EM_SETSEL, length, length);
    SendMessageW(g_log, EM_REPLACESEL, FALSE, reinterpret_cast<LPARAM>(text.c_str()));
    SendMessageW(g_log, EM_REPLACESEL, FALSE, reinterpret_cast<LPARAM>(L"\r\n"));
}

void SetStatus(const std::wstring& text) {
    SetWindowTextW(g_status, text.c_str());
}

void RefreshDocumentList() {
    SendMessageW(g_docList, LB_RESETCONTENT, 0, 0);

    for (const auto& document : g_state.documents) {
        const std::wstring row = FileNameOnly(document) + L"  [" + DocumentProfile(document) + L"]";
        SendMessageW(g_docList, LB_ADDSTRING, 0, reinterpret_cast<LPARAM>(row.c_str()));
    }

    std::wstringstream status;
    status << L"Документов выбрано: " << g_state.documents.size();
    SetStatus(status.str());
}

void RefreshFieldList() {
    ListView_DeleteAllItems(g_fieldList);

    for (int i = 0; i < static_cast<int>(g_state.fields.size()); ++i) {
        const auto& field = g_state.fields[i];

        LVITEMW item{};
        item.mask = LVIF_TEXT;
        item.iItem = i;
        item.iSubItem = 0;
        item.pszText = const_cast<wchar_t*>(field.name.c_str());
        ListView_InsertItem(g_fieldList, &item);
        ListView_SetItemText(g_fieldList, i, 1, const_cast<wchar_t*>(field.value.c_str()));
    }
}

std::vector<std::wstring> PickMultipleDocuments(HWND owner) {
    std::vector<wchar_t> buffer(65536, L'\0');

    OPENFILENAMEW ofn{};
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner = owner;
    ofn.lpstrFilter =
        L"Заполняемые Office-документы\0*.docx;*.pptx;*.xlsx\0"
        L"Word\0*.docx\0"
        L"Excel\0*.xlsx\0"
        L"PowerPoint\0*.pptx\0"
        L"Все файлы\0*.*\0";
    ofn.lpstrFile = buffer.data();
    ofn.nMaxFile = static_cast<DWORD>(buffer.size());
    ofn.Flags = OFN_ALLOWMULTISELECT | OFN_EXPLORER | OFN_FILEMUSTEXIST;
    ofn.lpstrTitle = L"Выберите документы для заполнения";

    if (!GetOpenFileNameW(&ofn)) {
        return {};
    }

    std::vector<std::wstring> result;
    const wchar_t* cursor = buffer.data();
    std::wstring directory = JoinPathListFromDialogBuffer(cursor);
    cursor += directory.size() + 1;

    if (*cursor == L'\0') {
        result.push_back(directory);
        return result;
    }

    while (*cursor != L'\0') {
        std::wstring fileName = cursor;
        result.push_back((std::filesystem::path(directory) / fileName).wstring());
        cursor += fileName.size() + 1;
    }

    return result;
}

std::wstring PickOneFile(HWND owner) {
    std::vector<wchar_t> buffer(MAX_PATH * 4, L'\0');

    OPENFILENAMEW ofn{};
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner = owner;
    ofn.lpstrFilter =
        L"Образцы документов\0*.jpg;*.jpeg;*.png;*.bmp;*.pdf;*.txt;*.csv;*.docx;*.doc;*.xlsx;*.xls\0"
        L"Удостоверения и сканы\0*.jpg;*.jpeg;*.png;*.bmp;*.pdf\0"
        L"Word\0*.docx;*.doc\0"
        L"Excel\0*.xlsx;*.xls\0"
        L"Текст/CSV\0*.txt;*.csv\0"
        L"Все файлы\0*.*\0";
    ofn.lpstrFile = buffer.data();
    ofn.nMaxFile = static_cast<DWORD>(buffer.size());
    ofn.Flags = OFN_EXPLORER | OFN_FILEMUSTEXIST;
    ofn.lpstrTitle = L"Выберите образец или заполненный документ";

    if (!GetOpenFileNameW(&ofn)) {
        return {};
    }

    return buffer.data();
}

std::wstring ComboText(HWND combo) {
    const int index = static_cast<int>(SendMessageW(combo, CB_GETCURSEL, 0, 0));
    if (index == CB_ERR) {
        return L"";
    }

    wchar_t text[160]{};
    SendMessageW(combo, CB_GETLBTEXT, index, reinterpret_cast<LPARAM>(text));
    return text;
}

void AddIfMissing(std::vector<FieldValue>& fields, const std::wstring& name, const std::wstring& value = L"") {
    const auto exists = std::find_if(fields.begin(), fields.end(), [&](const FieldValue& field) {
        return field.name == name;
    });

    if (exists == fields.end()) {
        fields.push_back({name, value});
    }
}

void AddIdentityFields(std::vector<FieldValue>& fields, const std::wstring& path) {
    AddIfMissing(fields, L"ФИО", GuessPersonNameFromFile(path));
    AddIfMissing(fields, L"ИИН", FindFirstIinLikeNumber(FileNameOnly(path)));
    AddIfMissing(fields, L"Номер удостоверения/паспорта");
    AddIfMissing(fields, L"Дата рождения");
    AddIfMissing(fields, L"Пол");
    AddIfMissing(fields, L"Гражданство");
    AddIfMissing(fields, L"Национальность");
    AddIfMissing(fields, L"Дата выдачи");
    AddIfMissing(fields, L"Срок действия");
    AddIfMissing(fields, L"Кем выдан");
    AddIfMissing(fields, L"Адрес регистрации");
}

void AddEmploymentContractFields(std::vector<FieldValue>& fields, const std::wstring& path) {
    AddIfMissing(fields, L"Работодатель", L"ALT Sound+");
    AddIfMissing(fields, L"БИН работодателя");
    AddIfMissing(fields, L"ФИО работника", GuessPersonNameFromFile(path));
    AddIfMissing(fields, L"ИИН работника", FindFirstIinLikeNumber(FileNameOnly(path)));
    AddIfMissing(fields, L"Номер удостоверения работника");
    AddIfMissing(fields, L"Дата выдачи удостоверения");
    AddIfMissing(fields, L"Адрес регистрации работника");
    AddIfMissing(fields, L"Дата договора", CurrentDateText());
    AddIfMissing(fields, L"Должность/роль работника");
}

void AddTaxDeductionFields(std::vector<FieldValue>& fields, const std::wstring& path) {
    AddIfMissing(fields, L"Налоговый агент", L"ТОО \"ALT SOUND+\"");
    AddIfMissing(fields, L"БИН налогового агента", L"090240020651");
    AddIfMissing(fields, L"ФИО физического лица", GuessPersonNameFromFile(path));
    AddIfMissing(fields, L"ИИН физического лица", FindFirstIinLikeNumber(FileNameOnly(path)));
    AddIfMissing(fields, L"Дата заявления", CurrentDateText());
    AddIfMissing(fields, L"Вычет ОПВ", L"да");
    AddIfMissing(fields, L"Вычет ВОСМС", L"да");
    AddIfMissing(fields, L"Базовый вычет", L"уточнить");
}

std::vector<FieldValue> ExtractFieldsLocally(const std::wstring& samplePath, const std::wstring& sampleKind) {
    std::vector<FieldValue> fields;

    const std::wstring ext = ExtensionLower(samplePath);
    fields.push_back({L"Тип образца", sampleKind});
    fields.push_back({L"Файл образца", FileNameOnly(samplePath)});
    fields.push_back({L"Формат", ext.empty() ? L"без расширения" : ext});

    if (ext == L".txt" || ext == L".csv") {
        fields.push_back({L"Статус извлечения", L"Текстовый образец: следующий шаг - чтение пар key=value"});
    } else if (ext == L".doc" || ext == L".docx" || ext == L".xls" || ext == L".xlsx") {
        fields.push_back({L"Статус извлечения", L"Office-образец принят: поля подготовлены по типу документа"});
    } else if (ext == L".pdf") {
        fields.push_back({L"Статус извлечения", L"PDF принят: для автосчитывания нужен локальный PDF/OCR-модуль"});
    } else {
        fields.push_back({L"Статус извлечения", L"Изображение принято: для автосчитывания нужен локальный OCR/штрихкод-модуль"});
    }

    if (sampleKind == L"Удостоверение личности" || sampleKind == L"Паспорт") {
        AddIdentityFields(fields, samplePath);
    } else if (sampleKind == L"Договор материальной ответственности") {
        AddEmploymentContractFields(fields, samplePath);
    } else if (sampleKind == L"Заявление на вычеты ИПН") {
        AddTaxDeductionFields(fields, samplePath);
    } else {
        AddIdentityFields(fields, samplePath);
        AddEmploymentContractFields(fields, samplePath);
        AddTaxDeductionFields(fields, samplePath);
    }

    return fields;
}

void AddDocuments(HWND owner) {
    const auto picked = PickMultipleDocuments(owner);
    if (picked.empty()) {
        return;
    }

    int added = 0;
    for (const auto& path : picked) {
        if (!IsSupportedTargetDocument(path)) {
            AppendLog(L"Пропущен неподдерживаемый файл: " + path);
            continue;
        }

        if (std::find(g_state.documents.begin(), g_state.documents.end(), path) == g_state.documents.end()) {
            g_state.documents.push_back(path);
            AppendLog(L"Добавлен " + DocumentProfile(path) + L": " + FileNameOnly(path));
            ++added;
        }
    }

    RefreshDocumentList();
    std::wstringstream log;
    log << L"Добавлено документов: " << added;
    AppendLog(log.str());
}

void RemoveSelectedDocument() {
    const int selected = static_cast<int>(SendMessageW(g_docList, LB_GETCURSEL, 0, 0));
    if (selected == LB_ERR) {
        return;
    }

    AppendLog(L"Удалён из списка: " + g_state.documents[selected]);
    g_state.documents.erase(g_state.documents.begin() + selected);
    RefreshDocumentList();
}

void PickSample(HWND owner) {
    const std::wstring picked = PickOneFile(owner);
    if (picked.empty()) {
        return;
    }

    if (!IsSupportedSample(picked)) {
        MessageBoxW(owner, L"Выберите изображение, PDF, Word, Excel, TXT или CSV.", L"Auto Adder", MB_ICONWARNING);
        return;
    }

    g_state.samplePath = picked;
    SetWindowTextW(g_samplePath, picked.c_str());
    SelectComboText(g_sampleKind, GuessSampleKind(picked));
    AppendLog(L"Выбран образец: " + picked);
    AppendLog(L"Тип образца определён как: " + ComboText(g_sampleKind));
}

void ExtractSampleData(HWND owner) {
    if (g_state.samplePath.empty()) {
        MessageBoxW(owner, L"Сначала выберите удостоверение, паспорт или другой образец.", L"Auto Adder", MB_ICONWARNING);
        return;
    }

    std::vector<FieldValue> extracted;
    std::wstring errorText;
    if (EngineExtractFields(g_state.samplePath, ComboText(g_sampleKind), extracted, errorText)) {
        g_state.fields = extracted;
        RefreshFieldList();
        AppendLog(L"Данные извлечены локально. Проверьте поля перед заполнением документов.");
        SetStatus(L"Данные извлечены. Дважды щёлкните по значению, чтобы исправить.");
        return;
    }

    AppendLog(L"Модуль извлечения: " + errorText);
    g_state.fields = ExtractFieldsLocally(g_state.samplePath, ComboText(g_sampleKind));
    RefreshFieldList();
    AppendLog(L"Использован резервный режим: заполните поля вручную и продолжайте.");
    MessageBoxW(owner, (errorText + L"\n\nПоля подготовлены вручную — проверьте и допишите значения.").c_str(), L"Auto Adder", MB_ICONWARNING);
}

void FillDocuments(HWND owner) {
    if (g_state.documents.empty()) {
        MessageBoxW(owner, L"Добавьте хотя бы один документ.", L"Auto Adder", MB_ICONWARNING);
        return;
    }

    if (g_state.fields.empty()) {
        MessageBoxW(owner, L"Сначала извлеките данные из удостоверения или паспорта.", L"Auto Adder", MB_ICONWARNING);
        return;
    }

    ReadFieldsFromListView();

    std::wstring summary;
    std::wstring errorText;
    if (!EngineFillDocuments(g_state.documents, g_state.fields, summary, errorText)) {
        AppendLog(errorText);
        MessageBoxW(owner, errorText.c_str(), L"Auto Adder", MB_ICONERROR);
        return;
    }

    AppendLog(summary);
    SetStatus(L"Документы заполнены локально. Резервные копии сохранены с суффиксом _backup.");
    MessageBoxW(owner, (summary + L"\n\nРезервные копии: *_backup.docx / *_backup.xlsx / *_backup.pptx").c_str(), L"Auto Adder", MB_ICONINFORMATION);
}

HWND CreateLabel(HWND parent, const wchar_t* text, int x, int y, int width, int height) {
    return CreateWindowExW(
        0, L"STATIC", text, WS_CHILD | WS_VISIBLE,
        x, y, width, height, parent, nullptr, GetModuleHandleW(nullptr), nullptr
    );
}

HWND CreateButton(HWND parent, int id, const wchar_t* text, int x, int y, int width, int height) {
    return CreateWindowExW(
        0, L"BUTTON", text, WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON,
        x, y, width, height, parent, reinterpret_cast<HMENU>(id), GetModuleHandleW(nullptr), nullptr
    );
}

void Layout(HWND hwnd) {
    RECT client{};
    GetClientRect(hwnd, &client);

    const int margin = 16;
    const int top = 64;
    const int bottom = 48;
    const int gap = 12;
    const int leftWidth = 390;
    const int rightX = margin + leftWidth + gap;
    const int rightWidth = client.right - rightX - margin;
    const int contentHeight = client.bottom - top - bottom;

    MoveWindow(g_docList, margin, top + 38, leftWidth, contentHeight - 108, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_ADD_DOCS), margin, client.bottom - 92, 122, 30, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_REMOVE_DOC), margin + 132, client.bottom - 92, 122, 30, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_CLEAR_DOCS), margin + 264, client.bottom - 92, 122, 30, TRUE);

    MoveWindow(g_samplePath, rightX, top + 38, rightWidth - 132, 28, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_PICK_SAMPLE), rightX + rightWidth - 120, top + 38, 120, 28, TRUE);
    MoveWindow(g_sampleKind, rightX, top + 104, 300, 180, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_EXTRACT), rightX + 314, top + 104, 160, 30, TRUE);

    MoveWindow(g_fieldList, rightX, top + 154, rightWidth, 250, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_FILL), rightX, top + 416, 210, 34, TRUE);
    MoveWindow(g_log, rightX, top + 486, rightWidth, contentHeight - 486, TRUE);
    MoveWindow(g_status, margin, client.bottom - 34, client.right - margin * 2, 22, TRUE);
}

void CreateControls(HWND hwnd) {
    HFONT uiFont = reinterpret_cast<HFONT>(GetStockObject(DEFAULT_GUI_FONT));

    CreateLabel(hwnd, kAppVersion, 16, 14, 300, 26);
    CreateLabel(hwnd, L"Локальная подготовка кадровых и налоговых документов без ИИ, облаков и отправки данных", 16, 40, 760, 20);

    CreateLabel(hwnd, L"Документы для заполнения", 16, 74, 300, 22);
    g_docList = CreateWindowExW(
        WS_EX_CLIENTEDGE, L"LISTBOX", nullptr,
        WS_CHILD | WS_VISIBLE | WS_VSCROLL | WS_HSCROLL | LBS_NOTIFY,
        16, 102, 390, 460, hwnd, reinterpret_cast<HMENU>(IDC_DOC_LIST), GetModuleHandleW(nullptr), nullptr
    );

    CreateButton(hwnd, IDC_ADD_DOCS, L"Добавить", 16, 600, 122, 30);
    CreateButton(hwnd, IDC_REMOVE_DOC, L"Убрать", 148, 600, 122, 30);
    CreateButton(hwnd, IDC_CLEAR_DOCS, L"Очистить", 280, 600, 122, 30);

    CreateLabel(hwnd, L"Образец или заполненный документ", 418, 74, 420, 22);
    g_samplePath = CreateWindowExW(
        WS_EX_CLIENTEDGE, L"EDIT", nullptr,
        WS_CHILD | WS_VISIBLE | ES_AUTOHSCROLL | ES_READONLY,
        418, 102, 420, 28, hwnd, reinterpret_cast<HMENU>(IDC_SAMPLE_PATH), GetModuleHandleW(nullptr), nullptr
    );
    CreateButton(hwnd, IDC_PICK_SAMPLE, L"Выбрать", 850, 102, 120, 28);

    CreateLabel(hwnd, L"Тип образца", 418, 142, 160, 22);
    g_sampleKind = CreateWindowExW(
        0, WC_COMBOBOXW, nullptr,
        WS_CHILD | WS_VISIBLE | CBS_DROPDOWNLIST,
        418, 168, 300, 180, hwnd, reinterpret_cast<HMENU>(IDC_SAMPLE_KIND), GetModuleHandleW(nullptr), nullptr
    );
    SendMessageW(g_sampleKind, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(L"Удостоверение личности"));
    SendMessageW(g_sampleKind, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(L"Паспорт"));
    SendMessageW(g_sampleKind, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(L"Договор материальной ответственности"));
    SendMessageW(g_sampleKind, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(L"Заявление на вычеты ИПН"));
    SendMessageW(g_sampleKind, CB_ADDSTRING, 0, reinterpret_cast<LPARAM>(L"Комплект кадровых документов"));
    SendMessageW(g_sampleKind, CB_SETCURSEL, 0, 0);
    CreateButton(hwnd, IDC_EXTRACT, L"Извлечь данные", 732, 168, 160, 30);

    CreateLabel(hwnd, L"Поля для проверки и переноса", 418, 218, 300, 22);
    g_fieldList = CreateWindowExW(
        WS_EX_CLIENTEDGE, WC_LISTVIEWW, nullptr,
        WS_CHILD | WS_VISIBLE | LVS_REPORT | LVS_SINGLESEL,
        418, 244, 650, 250, hwnd, reinterpret_cast<HMENU>(IDC_FIELD_LIST), GetModuleHandleW(nullptr), nullptr
    );
    ListView_SetExtendedListViewStyle(g_fieldList, LVS_EX_FULLROWSELECT | LVS_EX_GRIDLINES);

    LVCOLUMNW column{};
    column.mask = LVCF_TEXT | LVCF_WIDTH;
    column.cx = 230;
    column.pszText = const_cast<wchar_t*>(L"Поле");
    ListView_InsertColumn(g_fieldList, 0, &column);
    column.cx = 390;
    column.pszText = const_cast<wchar_t*>(L"Значение");
    ListView_InsertColumn(g_fieldList, 1, &column);

    CreateButton(hwnd, IDC_FILL, L"Заполнить документы", 418, 510, 210, 34);

    CreateLabel(hwnd, L"Журнал", 418, 566, 160, 22);
    g_log = CreateWindowExW(
        WS_EX_CLIENTEDGE, L"EDIT", nullptr,
        WS_CHILD | WS_VISIBLE | WS_VSCROLL | ES_MULTILINE | ES_READONLY,
        418, 592, 650, 86, hwnd, reinterpret_cast<HMENU>(IDC_LOG), GetModuleHandleW(nullptr), nullptr
    );

    g_status = CreateWindowExW(
        0, L"STATIC", L"Готово к работе. Все данные остаются на этом компьютере.",
        WS_CHILD | WS_VISIBLE,
        16, 690, 1000, 22, hwnd, reinterpret_cast<HMENU>(IDC_STATUS), GetModuleHandleW(nullptr), nullptr
    );

    const HWND controls[] = {
        g_docList, g_samplePath, g_sampleKind, g_fieldList, g_log, g_status,
        GetDlgItem(hwnd, IDC_ADD_DOCS), GetDlgItem(hwnd, IDC_REMOVE_DOC),
        GetDlgItem(hwnd, IDC_CLEAR_DOCS), GetDlgItem(hwnd, IDC_PICK_SAMPLE),
        GetDlgItem(hwnd, IDC_EXTRACT), GetDlgItem(hwnd, IDC_FILL)
    };

    for (HWND control : controls) {
        SendMessageW(control, WM_SETFONT, reinterpret_cast<WPARAM>(uiFont), TRUE);
    }

    AppendLog(std::wstring(kAppVersion) + L" запущен локально.");
    AppendLog(L"1) Выберите удостоверение или паспорт. 2) Нажмите «Извлечь данные». 3) Заполните документы.");
    if (FindPythonLauncher().empty() || FindEngineScript().empty()) {
        AppendLog(L"Внимание: для автоматической работы нужны Python 3 и engine/auto_adder_engine.py.");
    }
}

LRESULT CALLBACK WindowProc(HWND hwnd, UINT message, WPARAM wParam, LPARAM lParam) {
    switch (message) {
    case WM_CREATE:
        CreateControls(hwnd);
        return 0;

    case WM_SIZE:
        Layout(hwnd);
        return 0;

    case WM_COMMAND:
        switch (LOWORD(wParam)) {
        case IDC_ADD_DOCS:
            AddDocuments(hwnd);
            return 0;
        case IDC_REMOVE_DOC:
            RemoveSelectedDocument();
            return 0;
        case IDC_CLEAR_DOCS:
            g_state.documents.clear();
            RefreshDocumentList();
            AppendLog(L"Список документов очищен.");
            return 0;
        case IDC_PICK_SAMPLE:
            PickSample(hwnd);
            return 0;
        case IDC_EXTRACT:
            ExtractSampleData(hwnd);
            return 0;
        case IDC_FILL:
            FillDocuments(hwnd);
            return 0;
        default:
            break;
        }
        break;

    case WM_NOTIFY: {
        const auto* header = reinterpret_cast<NMHDR*>(lParam);
        if (header->idFrom == IDC_FIELD_LIST && header->code == NM_DBLCLK) {
            EditSelectedFieldValue(hwnd);
            return 0;
        }
        break;
    }

    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;

    default:
        break;
    }

    return DefWindowProcW(hwnd, message, wParam, lParam);
}

} // namespace

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int showCommand) {
    INITCOMMONCONTROLSEX commonControls{};
    commonControls.dwSize = sizeof(commonControls);
    commonControls.dwICC = ICC_LISTVIEW_CLASSES | ICC_STANDARD_CLASSES;
    InitCommonControlsEx(&commonControls);

    const wchar_t className[] = L"AutoAdderWin32";

    WNDCLASSW windowClass{};
    windowClass.lpfnWndProc = WindowProc;
    windowClass.hInstance = instance;
    windowClass.lpszClassName = className;
    windowClass.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    windowClass.hIcon = LoadIconW(instance, MAKEINTRESOURCEW(IDI_APP_ICON));
    windowClass.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_WINDOW + 1);

    RegisterClassW(&windowClass);

    g_mainWindow = CreateWindowExW(
        0,
        className,
        kAppVersion,
        WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT,
        CW_USEDEFAULT,
        kAppWidth,
        kAppHeight,
        nullptr,
        nullptr,
        instance,
        nullptr
    );

    if (!g_mainWindow) {
        return 0;
    }

    SendMessageW(g_mainWindow, WM_SETICON, ICON_BIG, reinterpret_cast<LPARAM>(LoadIconW(instance, MAKEINTRESOURCEW(IDI_APP_ICON))));
    SendMessageW(g_mainWindow, WM_SETICON, ICON_SMALL, reinterpret_cast<LPARAM>(LoadIconW(instance, MAKEINTRESOURCEW(IDI_APP_ICON))));

    ShowWindow(g_mainWindow, showCommand);
    UpdateWindow(g_mainWindow);

    MSG message{};
    while (GetMessageW(&message, nullptr, 0, 0)) {
        TranslateMessage(&message);
        DispatchMessageW(&message);
    }

    return static_cast<int>(message.wParam);
}
