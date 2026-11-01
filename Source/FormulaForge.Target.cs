using UnrealBuildTool;

public class FormulaForgeTarget : TargetRules
{
    public FormulaForgeTarget(TargetInfo target) : base(target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("FormulaForge");
    }
}
