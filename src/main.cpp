#include <iostream>
#include <string_view>

int main(int argc, char** argv) {
    for (int i = 1; i < argc; ++i) {
        if (std::string_view(argv[i]) == "--self-test") {
            std::cout << "harbor_karts self-test placeholder: ok\n";
            return 0;
        }
    }

    std::cout << "Harbor Karts skeleton. Build systems are ready.\n";
    return 0;
}
