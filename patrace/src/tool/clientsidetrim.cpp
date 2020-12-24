// Warning: This tool is a huge hack, use with care!

#include <utility>
#include <EGL/egl.h>
#include <GLES2/gl2.h>
#include <GLES3/gl31.h>
#include <GLES3/gl32.h>
#include <limits.h>
#include <unordered_map>

#include "tool/parse_interface.h"

#include "common/in_file.hpp"
#include "common/file_format.hpp"
#include "common/api_info.hpp"
#include "common/parse_api.hpp"
#include "common/trace_model.hpp"
#include "common/gl_utility.hpp"
#include "common/os.hpp"
#include "eglstate/context.hpp"
#include "tool/config.hpp"
#include "base/base.hpp"
#include "tool/utils.hpp"

static bool debug = false;
#define DEBUG_LOG(...) if (debug) DBG_LOG(__VA_ARGS__)

static void printHelp()
{
    std::cout <<
        "Usage : deduplicator [OPTIONS] trace_file.pat new_file.pat\n"
        "Options:\n"
        "  -h            Print help\n"
        "  -v            Print version\n"
        "  -d            Print debug info\n"
        ;
}

static void printVersion()
{
    std::cout << PATRACE_VERSION << std::endl;
}

static void writeout(common::OutFile &outputFile, common::CallTM *call)
{
    const unsigned int WRITE_BUF_LEN = 150*1024*1024;
    static char buffer[WRITE_BUF_LEN];
    char *dest = buffer;
    dest = call->Serialize(dest);
    outputFile.Write(buffer, dest-buffer);
}

int main(int argc, char **argv)
{
    int argIndex = 1;
    for (; argIndex < argc; ++argIndex)
    {
        std::string arg = argv[argIndex];

        if (arg[0] != '-')
        {
            break;
        }
        else if (arg == "-h")
        {
            printHelp();
            return 1;
        }
        else if (arg == "-d")
        {
            debug = true;
        }
        else if (arg == "-v")
        {
            printVersion();
            return 0;
        }
        else
        {
            std::cerr << "Error: Unknown option " << arg << std::endl;
            printHelp();
            return 1;
        }
    }

    if (argIndex + 2 > argc)
    {
        printHelp();
        return 1;
    }
    std::string source_trace_filename = argv[argIndex++];
    ParseInterface *inputFile = new ParseInterface(true);
    inputFile->setQuickMode(true);
    inputFile->setScreenshots(false);
    if (!inputFile->open(source_trace_filename))
    {
        std::cerr << "Failed to open for reading: " << source_trace_filename << std::endl;
        return 1;
    }

    common::OutFile outputFile;
    std::string target_trace_filename = argv[argIndex++];
    if (!outputFile.Open(target_trace_filename.c_str()))
    {
        std::cerr << "Failed to open for writing: " << target_trace_filename << std::endl;
        return 1;
    }
    Json::Value header = inputFile->header;
    Json::Value info;
    addConversionEntry(header, "inject_client_side_delete", source_trace_filename, info);
    Json::FastWriter writer;
    const std::string json_header = writer.write(header);
    outputFile.mHeader.jsonLength = json_header.size();
    outputFile.WriteHeader(json_header.c_str(), json_header.size());

    common::CallTM *call = nullptr;
    while ((call = inputFile->next_call())) {}
    const auto client_side_last_use = inputFile->client_side_last_use;
    const auto client_side_last_use_reason = inputFile->client_side_last_use_reason;
    inputFile->close();
    delete inputFile;
    inputFile = new ParseInterface(true);
    if (!inputFile->open(source_trace_filename))
    {
        std::cerr << "Failed to open for reading again: " << source_trace_filename << std::endl;
        return 1;
    }
    std::map<int, int> callno_to_client_side_last_use; // call no, client id; thread id implicit
    for (const auto& thread : client_side_last_use) // pair of thread : (pair of cs id, call number)
    {
        printf("Thread %d has %d cs:call pairs\n", thread.first, (int)thread.second.size());
        for (const auto& pair : thread.second)
        {
            callno_to_client_side_last_use[pair.second] = pair.first;
            DBG_LOG("\tt%d cs%d call%d endpoint=%s\n", thread.first, pair.first, pair.second, client_side_last_use_reason.at(thread.first).at(pair.first).c_str());
        }
    }
    int count = 0;
    while ((call = inputFile->next_call()))
    {
        writeout(outputFile, call);
        if (callno_to_client_side_last_use.count(call->mCallNo) > 0)
        {
            common::CallTM deletion("glDeleteClientSideBuffer");
            deletion.mArgs.push_back(new common::ValueTM(callno_to_client_side_last_use[call->mCallNo]));
            deletion.mTid = call->mTid;
            writeout(outputFile, &deletion);
            count++;
        }
    }
    inputFile->close();

    outputFile.Close();
    printf("Injected %d deletion calls\n", count);
    return 0;
}
