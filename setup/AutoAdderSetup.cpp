#ifndef UNICODE
#define UNICODE
#endif

#ifndef _UNICODE
#define _UNICODE
#endif

#include <windows.h>
#include <shlobj.h>
#include <shobjidl.h>

#include "resource.h"

#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

namespace {

std::wstring LastErrorText(const std::wstring& prefix) {
    DWORD error = GetLastError();
    wchar_t* message = nullptr;
    FormatMessageW(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
        nullptr,
        error,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        reinterpret_cast<LPWSTR>(&message),
        0,
        nullptr
    );

    std::wstring result = prefix;
    if (message) {
        result += L"\n\n";
        result += message;
        LocalFree(message);
    }
    return result;
}

std::filesystem::path KnownFolder(REFKNOWNFOLDERID folderId) {
    PWSTR path = nullptr;
    HRESULT hr = SHGetKnownFolderPath(folderId, KF_FLAG_DEFAULT, nullptr, &path);
    if (FAILED(hr) || !path) {
        return {};
    }

    std::filesystem::path result(path);
    CoTaskMemFree(path);
    return result;
}

std::wstring Quote(const std::filesystem::path& path) {
    std::wstring value = path.wstring();
    std::wstring quoted = L"\"";
    for (wchar_t ch : value) {
        if (ch == L'"') {
            quoted += L'\\';
        }
        quoted += ch;
    }
    quoted += L"\"";
    return quoted;
}

bool RunAndWait(const std::wstring& command, DWORD& exitCode) {
    std::vector<wchar_t> buffer(command.begin(), command.end());
    buffer.push_back(L'\0');

    STARTUPINFOW startup{};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESHOWWINDOW;
    startup.wShowWindow = SW_HIDE;

    PROCESS_INFORMATION process{};
    BOOL created = CreateProcessW(
        nullptr,
        buffer.data(),
        nullptr,
        nullptr,
        FALSE,
        CREATE_NO_WINDOW,
        nullptr,
        nullptr,
        &startup,
        &process
    );

    if (!created) {
        return false;
    }

    WaitForSingleObject(process.hProcess, INFINITE);
    GetExitCodeProcess(process.hProcess, &exitCode);
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return true;
}

bool ExtractPayloadZip(const std::filesystem::path& zipPath, std::wstring& error) {
    HRSRC resource = FindResourceW(nullptr, MAKEINTRESOURCEW(IDR_PAYLOAD_ZIP), RT_RCDATA);
    if (!resource) {
        error = LastErrorText(L"Could not find embedded Auto-adder.zip.");
        return false;
    }

    HGLOBAL loaded = LoadResource(nullptr, resource);
    if (!loaded) {
        error = LastErrorText(L"Could not load embedded Auto-adder.zip.");
        return false;
    }

    DWORD size = SizeofResource(nullptr, resource);
    void* data = LockResource(loaded);
    if (!data || size == 0) {
        error = L"Embedded Auto-adder.zip is empty.";
        return false;
    }

    std::ofstream out(zipPath, std::ios::binary);
    if (!out) {
        error = L"Could not write temporary payload zip:\n\n" + zipPath.wstring();
        return false;
    }

    out.write(reinterpret_cast<const char*>(data), size);
    return static_cast<bool>(out);
}

bool CreateDesktopShortcut(const std::filesystem::path& target, const std::filesystem::path& shortcutPath, std::wstring& error) {
    HRESULT initialized = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    bool shouldUninitialize = SUCCEEDED(initialized);
    if (FAILED(initialized) && initialized != RPC_E_CHANGED_MODE) {
        error = L"Could not initialize Windows shortcut API.";
        return false;
    }

    IShellLinkW* link = nullptr;
    HRESULT hr = CoCreateInstance(CLSID_ShellLink, nullptr, CLSCTX_INPROC_SERVER, IID_IShellLinkW, reinterpret_cast<void**>(&link));
    if (FAILED(hr) || !link) {
        if (shouldUninitialize) CoUninitialize();
        error = L"Could not create Windows shortcut object.";
        return false;
    }

    link->SetPath(target.c_str());
    link->SetWorkingDirectory(target.parent_path().c_str());
    link->SetIconLocation(target.c_str(), 0);
    link->SetDescription(L"Auto Adder");

    IPersistFile* persist = nullptr;
    hr = link->QueryInterface(IID_IPersistFile, reinterpret_cast<void**>(&persist));
    if (SUCCEEDED(hr) && persist) {
        hr = persist->Save(shortcutPath.c_str(), TRUE);
        persist->Release();
    }
    link->Release();

    if (shouldUninitialize) {
        CoUninitialize();
    }

    if (FAILED(hr)) {
        error = L"Could not save desktop shortcut:\n\n" + shortcutPath.wstring();
        return false;
    }

    return true;
}

std::filesystem::path FindExtractedApp(const std::filesystem::path& extractDir) {
    std::filesystem::path direct = extractDir / L"AutoAdder.exe";
    if (std::filesystem::exists(direct)) {
        return extractDir;
    }

    for (const auto& entry : std::filesystem::directory_iterator(extractDir)) {
        if (!entry.is_directory()) {
            continue;
        }

        std::filesystem::path candidate = entry.path() / L"AutoAdder.exe";
        if (std::filesystem::exists(candidate)) {
            return entry.path();
        }
    }

    return {};
}

void ShowError(const std::wstring& message) {
    MessageBoxW(nullptr, message.c_str(), L"Auto Adder Setup", MB_ICONERROR | MB_OK);
}

}  // namespace

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    try {
        std::filesystem::path localAppData = KnownFolder(FOLDERID_LocalAppData);
        std::filesystem::path desktop = KnownFolder(FOLDERID_Desktop);
        if (localAppData.empty() || desktop.empty()) {
            ShowError(L"Could not locate Windows user folders.");
            return 1;
        }

        std::filesystem::path installDir = localAppData / L"AutoAdder";
        std::filesystem::path tempRoot = std::filesystem::temp_directory_path() / L"AutoAdderSetup";
        std::filesystem::path payloadZip = tempRoot / L"Auto-adder.zip";
        std::filesystem::path extractDir = tempRoot / L"extract";

        std::error_code ignored;
        std::filesystem::remove_all(tempRoot, ignored);
        std::filesystem::create_directories(extractDir);

        std::wstring error;
        if (!ExtractPayloadZip(payloadZip, error)) {
            ShowError(error);
            return 1;
        }

        DWORD exitCode = 0;
        std::wstring command = L"tar.exe -xf " + Quote(payloadZip) + L" -C " + Quote(extractDir);
        if (!RunAndWait(command, exitCode) || exitCode != 0) {
            ShowError(L"Could not extract Auto Adder package.");
            return 1;
        }

        std::filesystem::path extractedApp = FindExtractedApp(extractDir);
        if (extractedApp.empty()) {
            ShowError(L"Extracted package does not contain AutoAdder.exe.");
            return 1;
        }

        std::filesystem::remove_all(installDir, ignored);
        std::filesystem::create_directories(installDir);
        std::filesystem::copy(
            extractedApp,
            installDir,
            std::filesystem::copy_options::recursive | std::filesystem::copy_options::overwrite_existing
        );

        std::filesystem::path appExe = installDir / L"AutoAdder.exe";
        std::filesystem::path shortcut = desktop / L"Auto Adder.lnk";
        if (!CreateDesktopShortcut(appExe, shortcut, error)) {
            ShowError(error);
            return 1;
        }

        std::filesystem::remove_all(tempRoot, ignored);

        ShellExecuteW(nullptr, L"open", appExe.c_str(), nullptr, installDir.c_str(), SW_SHOWNORMAL);
        MessageBoxW(nullptr, L"Auto Adder is installed. A desktop shortcut was created.", L"Auto Adder Setup", MB_ICONINFORMATION | MB_OK);
        return 0;
    } catch (const std::exception&) {
        ShowError(L"Unexpected setup error.");
        return 1;
    }
}
