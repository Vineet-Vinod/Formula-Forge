using System.IO;
using UnrealBuildTool;

public class FormulaForge : ModuleRules
{
    public FormulaForge(ReadOnlyTargetRules target) : base(target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        bUseUnity = false;
        CppStandard = CppStandardVersion.Cpp20;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine", "InputCore" });
        PrivateDependencyModuleNames.AddRange(new[] { "RenderCore", "RHI", "Json", "ImageCore", "SlateCore", "Slate", "MoviePlayer" });
        PublicIncludePaths.Add(Path.GetFullPath(Path.Combine(ModuleDirectory, "Native")));
    }
}
