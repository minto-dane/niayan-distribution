-- SPDX-License-Identifier: MIT
-- Synthetic scoped observer; native catalog/original readers remain real.
with Ada.Command_Line; with Ada.Directories; with Ada.Unchecked_Deallocation; with Ada.Text_IO;
with Interfaces.C; with System;
with MC_Clock; with MC_Codec; with MC_FS; with MC_Hex; with MC_Posix; with MC_Runtime;
with MC_SHA256; with MC_Store; with MC_Types; use MC_Types;
with Pkg_Archive_Supply; with Pkg_Catalog_Retention; with Pkg_Catalog_Store;
with Pkg_Deb_Metadata; with Pkg_Deb_Payload; with Pkg_Generation_Descriptor;
with Pkg_Payload_Index; with Pkg_Selected_Catalog; with Pkg_Supply_Map; with Pkg_Supply_Policy;
with Test_Support; use Test_Support;
procedure Run_Shared_Preflight_Benchmark with SPARK_Mode => Off is
   package M renames Pkg_Supply_Map; package C renames Pkg_Selected_Catalog;
   package X renames Pkg_Payload_Index; package GD renames Pkg_Generation_Descriptor;
   use type Interfaces.C.int; use type Interfaces.C.unsigned; use type Interfaces.C.unsigned_long_long;
   use type Byte; use type Wide; use type MC_FS.Entry_Kind;
   type Counter_Array is array (Positive range <>) of Counter;
   type Digest_Array is array (Positive range <>) of Digest;
   Store : MC_Store.Store; Media, CAS : MC_FS.Root; File : MC_FS.File;
   Status : Outcome; Now, Boot, Deadline, Until_Time : Counter;
   Target, Initial, Update_Target, Bad_Target : M.Context;
   Trusted : M.Authorities (1 .. 1); No_Trust : M.Authorities (1 .. 0);
   Rows : M.Sources (1 .. 2); Nothing : M.Sources (1 .. 0);
   SK : Bytes (1 .. 64); Seed : constant Digest := (others => 101);
   Upstream : array (1 .. 4) of Digest;
   Address, Initial_Map, Update_Map, Other : Digest;
   Wire, Changed : Bytes (1 .. M.Header_Size + 2 * M.Entry_Size + 1);
   Used : Natural;
   type Observation_Access is access Pkg_Deb_Metadata.Observation;
   procedure Free is new Ada.Unchecked_Deallocation (Pkg_Deb_Metadata.Observation, Observation_Access);
   Observation : Observation_Access := null;
   function Keypair (PK, SK, Seed : System.Address) return Interfaces.C.int
     with Import, Convention => C, External_Name => "crypto_sign_seed_keypair";
   function Sign (Signature, Length, Message : System.Address;
      Size : Interfaces.C.unsigned_long_long; SK : System.Address) return Interfaces.C.int
     with Import, Convention => C, External_Name => "crypto_sign_detached";
   procedure Need (Label_Text : String) is
   begin Expect (Status = OK, Label_Text & Outcome'Image (Status)); end Need;
   function Object_Path (Hash : Digest) return String is
      Hex : constant String := MC_Hex.Encode (Hash);
   begin return "objects/" & Hex (1 .. 2) & "/" & Hex (3 .. 64); end Object_Path;
   procedure Import (Name : String; Row : out M.Source) is
      Frame : Bytes (1 .. Pkg_Archive_Supply.Wire_Size) := (others => 0);
      Domain : constant String := "NiaOS/archive-supply/v1";
      Message : Bytes (1 .. 2 + Domain'Length + Pkg_Archive_Supply.Body_Size);
      Length : aliased Interfaces.C.unsigned_long_long := 0;
   begin
      MC_FS.Open_Read (Media, Name, File, Status); Need ("fixture open");
      MC_Store.Import_File (Store, File, MC_Store.Max_Object_Size, Row.Original, Status); Need ("original import"); MC_FS.Close (File);
      Observation := new Pkg_Deb_Metadata.Observation;
      Pkg_Deb_Metadata.Inspect (Store, Row.Original, Deadline, Observation.all, Status); Need ("original control");
      Row.Control := Observation.Control; Free (Observation);
      Frame (1 .. 8) := (78, 73, 65, 83, 85, 80, 48, 49); Frame (9 .. 40) := Trusted (1).Scope;
      Frame (41 .. 72) := Upstream (1); Frame (73 .. 104) := Row.Original; Frame (105 .. 136) := Row.Control;
      Frame (137 .. 168) := Upstream (2); Frame (169 .. 200) := Upstream (3); Frame (201 .. 232) := Upstream (4);
      MC_Codec.Put64 (Frame, 233, 7); MC_Codec.Put64 (Frame, 241, Wide (Now)); MC_Codec.Put64 (Frame, 249, Wide (Now + 600));
      MC_Codec.Put16 (Message, 1, Domain'Length);
      for I in Domain'Range loop Message (I + 2) := Byte (Character'Pos (Domain (I))); end loop;
      Message (Domain'Length + 3 .. Message'Last) := Frame (1 .. 256);
      Expect (Sign (Frame (257)'Address, Length'Address, Message'Address, Message'Length, SK'Address) = 0
         and then Length = 64, "synthetic observer signs exact domain");
      MC_Store.Put (Store, Frame, Row.Receipt, Status); Need ("retain supply receipt");
   end Import;
   procedure Catalog (Items : M.Sources) is
      Value : C.Catalog; Payload : X.Index; Inventory : Pkg_Deb_Payload.Inventory;
      Selection : C.Selection (Items'Range);
   begin
      for I in Items'Range loop
         Selection (I) := (Items (I).Original, Items (I).Control);
         Pkg_Deb_Payload.Stage (Store, Items (I).Original, Deadline, Inventory, Status); Need ("native payload");
         X.Add (Payload, Inventory, Deadline, Status); Need ("payload source");
         C.Add (Value, Store, Items (I).Original, Deadline, Status); Need ("catalog source");
      end loop;
      X.Seal (Payload, Deadline, Status); Need ("seal payload");
      C.Seal (Value, Selection, Payload, Deadline, Status); Need ("seal catalog");
      Pkg_Catalog_Store.Save (Store, Value, Deadline, Target.Catalog, Status); Need ("save catalog");
      Pkg_Catalog_Retention.Prepare (Store, Target.Catalog, Deadline, Target.Closure, Status); Need ("catalog closure");
   end Catalog;
   procedure Prepare (Items : M.Sources) is
   begin
      M.Prepare (Store, Target, Items, Trusted, Now, Deadline, Address, Until_Time, Status); Need ("prepare exact supply map");
      Expect (Address /= Zero_Digest and then (if Items'Length = 0 then Until_Time = 0 else Until_Time = Now + 600), "map identity and expiry");
      M.Verify (Store, Address, Target, Trusted, Now, Deadline, Until_Time, Status); Need ("reverify exact map");
      M.Check_Retention (Store, Address, Target.Catalog, Target.Closure, Deadline, Status); Need ("historical retention");
   end Prepare;
   procedure Reject_Items (Items : M.Sources; Label_Text : String) is
   begin
      Address := Initial_Map; Until_Time := 123;
      M.Prepare (Store, Target, Items, Trusted, Now, Deadline, Address, Until_Time, Status);
      Expect (Status /= OK and then Address = Zero_Digest and then Until_Time = 0, Label_Text);
   end Reject_Items;
   procedure Reject (Data : Bytes; Label_Text : String) is
   begin
      MC_Store.Put (Store, Data, Other, Status); Need ("retain malformed map"); Until_Time := 123;
      M.Verify (Store, Other, Target, Trusted, Now, Deadline, Until_Time, Status);
      Expect (Status /= OK and then Until_Time = 0, Label_Text);
   end Reject;
   procedure Before (Value : M.Context) is
   begin
      Target.Before := (Root_ID => Target.Root_ID, Stage_ID => (others => 103),
         Manifest => Value.Closure, Catalog => Value.Catalog, Generation => 1, Previous => Zero_Digest);
      -- A structurally valid retained descriptor is a fixture, not accepted state.
      MC_Store.Put (Store, GD.Encode (Target.Before), Other, Status); Need ("retained predecessor fixture");
      Target.Before_Closure := Value.Closure;
   end Before;
   procedure Check_Policy is
      package P renames Pkg_Supply_Policy;
      Value : P.Snapshot; Good, Bad : Digest; N : Natural;
      Frame, Damaged : Bytes (1 .. P.Max_Bytes + 1);
      High : M.Authorities (Positive'Last .. Positive'Last) := (others => Trusted (1));
   begin
      P.Prepare (Store, Initial_Map, Target, High, Now, Deadline, Good, Until_Time, Status); Need ("policy highest array bound");
      P.Load (Store, Good, Deadline, Value, Status); Need ("canonical policy load");
      Expect (Value.Map = Initial_Map and then Value.Observed_At = Now and then Value.Count = 1, "retained policy subject");
      P.Prepare (Store, Initial_Map, Target, Trusted, Now, Deadline, Bad, Until_Time, Status); Need ("policy deterministic preparation");
      Expect (Bad = Good, "policy ignores external array bounds");
      P.Verify_New (Store, Good, Target, Trusted, Now, Deadline, Until_Time, Status); Need ("independent fresh policy");
      P.Verify_New (Store, Good, Target, Trusted, Now + 600, Deadline, Until_Time, Status);
      Expect (Status = Stale and then Until_Time = 0, "expired receipt cannot admit a new plan");
      P.Recheck_Recorded (Store, Good, Target, Trusted, Now + 600, Deadline, Status); Need ("recorded signature observation survives UTC expiry");
      P.Check_Retention (Store, Good, Target.Catalog, Target.Closure, Deadline, Status); Need ("policy roots complete map retention");
      P.Verify_New (Store, Good, Target, No_Trust, Now, Deadline, Until_Time, Status);
      Expect (Status = Denied and then Until_Time = 0, "stored keys never grant fresh trust");
      P.Recheck_Recorded (Store, Good, Target, No_Trust, Now + 600, Deadline, Status);
      Expect (Status = Denied, "recorded keys still require independent current trust");
      for D of Counter_Array'(0, Counter'Last) loop
         P.Recheck_Recorded (Store, Good, Target, Trusted, Now + 600, D, Status);
         Expect (Status /= OK, "historical check still has a live I/O deadline");
      end loop;
      MC_Store.Read_Object (Store, Good, Frame, N, Status); Need ("policy framing");
      Expect (N = P.Header_Size + P.Entry_Size, "canonical policy length");
      for I in 1 .. N loop
         Damaged := Frame; Damaged (I) := Damaged (I) xor 1;
         MC_Store.Put (Store, Damaged (1 .. N), Bad, Status); Need ("retain changed policy");
         P.Verify_New (Store, Bad, Target, Trusted, Now, Deadline, Until_Time, Status);
         Expect (Status /= OK and then Until_Time = 0, "mutated policy never authenticates itself");
      end loop;
      for Size in N - 1 .. N + 1 loop
         if Size /= N then
            MC_Store.Put (Store, Frame (1 .. Size), Bad, Status); Need ("retain noncanonical policy length");
            P.Load (Store, Bad, Deadline, Value, Status);
            Expect (Status /= OK and then Value.Map = Zero_Digest and then Value.Count = 0, "policy load clears malformed output");
         end if;
      end loop;
      declare
         Pair : M.Authorities (5 .. 6) := (others => Trusted (1)); Swap : Pkg_Archive_Supply.Authority;
         First, Second : Digest; Excess : M.Authorities (1 .. M.Max_Authorities + 1) := (others => Trusted (1));
      begin
         Pair (5).Scope := (others => 103);
         P.Prepare (Store, Initial_Map, Target, Pair, Now, Deadline, First, Until_Time, Status); Need ("unordered full independent policy");
         Swap := Pair (5); Pair (5) := Pair (6); Pair (6) := Swap;
         P.Prepare (Store, Initial_Map, Target, Pair, Now, Deadline, Second, Until_Time, Status); Need ("canonical full independent policy");
         Expect (First = Second, "policy source ordering does not affect bytes");
         P.Verify_New (Store, First, Target, Pair, Now, Deadline, Until_Time, Status); Need ("canonical policy matches reordered current authority");
         Pair (6) := Pair (5);
         P.Prepare (Store, Initial_Map, Target, Pair, Now, Deadline, Bad, Until_Time, Status);
         Expect (Status = Conflict and then Bad = Zero_Digest and then Until_Time = 0, "duplicate policy scope rejected");
         P.Prepare (Store, Initial_Map, Target, Excess, Now, Deadline, Bad, Until_Time, Status);
         Expect (Status = Invalid_Input and then Bad = Zero_Digest and then Until_Time = 0, "oversized authority policy bounded before I/O");
      end;
      M.Verify_Interval (Store, Initial_Map, Target, Trusted, Now - 1, Now, Deadline, Until_Time, Status);
      Expect (Status = Stale and then Until_Time = 0, "fresh plan cannot invent an earlier observation");
      M.Verify_Interval (Store, Initial_Map, Target, Trusted, Now + 1, Now, Deadline, Until_Time, Status);
      Expect (Status = Invalid_Input and then Until_Time = 0, "future retained observation refused at entry");
   end Check_Policy;
   procedure External_Fixture is
      procedure Read_Input (Name : String; Hash : out Digest) is
      begin
         MC_FS.Open_Read (Media, Name, File, Status); Need ("external input");
         MC_Store.Import_File (Store, File, MC_Store.Max_Object_Size, Hash, Status); Need ("external import"); MC_FS.Close (File);
      end Read_Input;
   begin
      Expect (Ada.Command_Line.Argument (3) = "external", "explicit external fixture mode");
      Read_Input ("original.deb", Rows (1).Original); Read_Input ("control", Rows (1).Control);
      Read_Input ("receipt", Rows (1).Receipt); Read_Input ("policy", Other); Read_Input ("InRelease", Other);
      Read_Input ("Packages", Other); Read_Input ("keyring", Other);
      Read_Input ("public-key", Other); MC_Store.Read_Object (Store, Other, Trusted (1).Key, Used, Status); Need ("independent key");
      Expect (Used = 32, "public key size");
      Read_Input ("scope", Other); MC_Store.Read_Object (Store, Other, Trusted (1).Scope, Used, Status); Need ("independent scope");
      Expect (Used = 32, "scope size");
      Trusted (1).Minimum_Epoch := 7; Trusted (1).Maximum_Age := 1_800;
      Target.Root_ID := (others => 104); Catalog (Rows (1 .. 1));
      M.Prepare (Store, Target, Rows (1 .. 1), Trusted, Now, Deadline, Address, Until_Time, Status);
      if Status /= OK then Expect (Address = Zero_Digest and then Until_Time = 0, "external failure clears map outputs"); end if;
      Need ("external map");
      Expect (Until_Time > Now and then Until_Time <= Now + 300, "actual receipt expiry retained");
      M.Verify (Store, Address, Target, Trusted, Now, Deadline, Until_Time, Status); Need ("external revalidation");
      Ada.Text_IO.Put_Line ("SUPPLY_MAP " & MC_Hex.Encode (Address));
      Ada.Text_IO.Put_Line ("SUPPLY_CATALOG " & MC_Hex.Encode (Target.Catalog));
      Ada.Text_IO.Put_Line ("SUPPLY_CLOSURE " & MC_Hex.Encode (Target.Closure));
   end External_Fixture;
begin
   Expect (Ada.Command_Line.Argument_Count = 3, "fresh CAS, media, bounded package count");
   MC_Runtime.Initialize (Status); Need ("runtime");
   Expect (MC_Posix.Euid /= 0, "benchmark refuses UID0");
   MC_Store.Initialize (Ada.Command_Line.Argument (1), Store, Status); Need ("private CAS");
   MC_FS.Open_Root (Ada.Directories.Full_Name (Ada.Command_Line.Argument (2)), Media, Status); Need ("media");
   MC_Clock.Boottime_Milliseconds (Boot, Status); Need ("boottime"); Deadline := Boot + 600_000;
   Now := 1_000;
   Trusted (1) := (Scope => (others => 102), Minimum_Epoch => 7, Maximum_Age => 1_800, others => <>);
   Expect (Keypair (Trusted (1).Key'Address, SK'Address, Seed'Address) = 0, "synthetic observer key");
   for I in Upstream'Range loop
      declare Img : constant String := Integer'Image (I); begin
         MC_FS.Open_Read (Media, "shared-" & Img (Img'First + 1 .. Img'Last), File, Status); Need ("shared input");
         MC_Store.Import_File (Store, File, MC_Store.Max_Object_Size, Upstream (I), Status); Need ("shared import"); MC_FS.Close (File);
         Ada.Text_IO.Put_Line ("BENCH_SHARED " & MC_Hex.Encode (Upstream (I)));
      end;
   end loop;
   declare
      Count : constant Positive := Positive'Value (Ada.Command_Line.Argument (3));
      Started, Finished : Counter; Temp : M.Source;
   begin
      Expect (Count <= 256, "bounded package count");
      declare Items : M.Sources (1 .. Count); begin
         for I in Items'Range loop
            declare Img : constant String := Integer'Image (I); begin
               Import ("package-" & Img (Img'First + 1 .. Img'Last) & ".deb", Items (I));
            end;
         end loop;
         for I in Items'First + 1 .. Items'Last loop
            for J in reverse Items'First + 1 .. I loop
               exit when Items (J - 1).Original < Items (J).Original;
               Temp := Items (J - 1); Items (J - 1) := Items (J); Items (J) := Temp;
            end loop;
         end loop;
         Target.Root_ID := (others => 104); Catalog (Items);
         for Phase in 1 .. 3 loop
            Ada.Text_IO.Put_Line ("BENCH_PHASE" & Integer'Image (Phase) & " BEGIN"); Ada.Text_IO.Flush;
            MC_Clock.Boottime_Milliseconds (Started, Status); Need ("start");
            case Phase is
               when 1 => M.Prepare (Store, Target, Items, Trusted, Now, Deadline, Address, Until_Time, Status);
               when 2 => M.Verify (Store, Address, Target, Trusted, Now, Deadline, Until_Time, Status);
               when others => M.Check_Retention (Store, Address, Target.Catalog, Target.Closure, Deadline, Status);
            end case;
            Need ("benchmark phase");
            MC_Clock.Boottime_Milliseconds (Finished, Status); Need ("finish");
            Ada.Text_IO.Put_Line ("BENCH_PHASE" & Integer'Image (Phase) & " END" & Counter'Image (Finished - Started)); Ada.Text_IO.Flush;
         end loop;
         Ada.Text_IO.Put_Line ("BENCH_MAP " & MC_Hex.Encode (Address));
         Ada.Text_IO.Put_Line ("BENCH_CATALOG " & MC_Hex.Encode (Target.Catalog));
         Ada.Text_IO.Put_Line ("BENCH_CLOSURE " & MC_Hex.Encode (Target.Closure));
      end;
   end;
   MC_FS.Close (Media); MC_Store.Close (Store); Report;
exception when others => Free (Observation); MC_FS.Close (File); MC_FS.Close (Media); MC_Store.Close (Store); raise;
end Run_Shared_Preflight_Benchmark;
