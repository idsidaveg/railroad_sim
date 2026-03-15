import sys
from pathlib import Path
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from railroad_sim.domain.enums import (
    BoxCarService,
    BoxCarThermalProtection,
    BoxCarType,
    CabooseType,
    GondolaService,
    GondolaType,
    IntermodalCarType,
    MotivePowerType,
    TankCarService,
    TankCarThermalProtection,
    TankCarType,
)
from railroad_sim.domain.equipment.boxcar import BoxCar
from railroad_sim.domain.equipment.caboose import Caboose
from railroad_sim.domain.equipment.gondola import Gondola
from railroad_sim.domain.equipment.intermodalcar import IntermodalCar
from railroad_sim.domain.equipment.locomotive import Locomotive
from railroad_sim.domain.equipment.tankcar import TankCar


class DebugEquipmentSet(TypedDict):
    loco: Locomotive
    boxcar: BoxCar
    tankcar: TankCar
    intermodal: IntermodalCar
    gondola: Gondola
    caboose: Caboose


def build_debug_equipment() -> DebugEquipmentSet:
    """
    Create one example of each currently defined equipment subtype.
    """
    loco = Locomotive(
        reporting_mark="BNSF",
        road_number="4721",
        motive_power_type=MotivePowerType.DIESEL,
        horsepower=4400,
        builder="GE",
        model="ES44DC",
        axle_count=6,
        energy_capacity=5000.0,
    )

    boxcar = BoxCar(
        reporting_mark="UP",
        road_number="500001",
        boxcar_type=BoxCarType.REFRIGERATED,
        service_type=BoxCarService.FOOD_GRADE,
        thermal_protection=BoxCarThermalProtection.REFRIGERATED,
        inside_length_ft=60.0,
        cubic_capacity_ft3=7500.0,
        door_count=2,
        load_limit_lbs=140000.0,
    )

    tankcar = TankCar(
        reporting_mark="UTLX",
        road_number="100001",
        tankcar_type=TankCarType.GENERAL_SERVICE,
        service_type=TankCarService.FOOD_GRADE,
        thermal_protection=TankCarThermalProtection.INSULATED,
        capacity_gallons=30000.0,
        is_pressurized=False,
        load_limit_lbs=180000.0,
        tank_material="stainless_steel",
    )

    intermodal = IntermodalCar(
        reporting_mark="DTTX",
        road_number="200001",
        intermodal_car_type=IntermodalCarType.WELL_CAR,
        well_count=1,
        max_load_units=2,
        articulated=False,
        load_limit_lbs=180000.0,
    )

    gondola = Gondola(
        reporting_mark="UP",
        road_number="700001",
        gondola_type=GondolaType.HIGH_SIDE,
        service_type=GondolaService.SCRAP,
        inside_length_ft=52.0,
        cubic_capacity_ft3=5000.0,
        load_limit_lbs=160000.0,
    )

    caboose = Caboose(
        reporting_mark="UP",
        road_number="900001",
        caboose_type=CabooseType.CUPOLA,
        crew_capacity=4,
        occupied=False,
        has_stove=True,
        has_cupola=True,
    )

    return {
        "loco": loco,
        "boxcar": boxcar,
        "tankcar": tankcar,
        "intermodal": intermodal,
        "gondola": gondola,
        "caboose": caboose,
    }


def print_equipment_summary(equipment: DebugEquipmentSet) -> None:
    """
    Print a concise summary of each equipment object.
    """
    print("Equipment Summary")
    print("=" * 80)

    keys = ("loco", "boxcar", "tankcar", "intermodal", "gondola", "caboose")

    for key in keys:
        car = equipment[key]
        print(f"{key.upper():<12} {car}")
        print(f"  equipment_class : {car.equipment_class}")
        print(f"  asset_id        : {car.asset_id}")
        print(f"  front_coupler   : {car.front_coupler}")
        print(f"  rear_coupler    : {car.rear_coupler}")
        print()


def demo_basic_loading(equipment: DebugEquipmentSet) -> None:
    """
    Demonstrate basic loading/unloading flows for the equipment types
    that currently support it.
    """
    print("Load / Unload Demo")
    print("=" * 80)

    boxcar = equipment["boxcar"]
    tankcar = equipment["tankcar"]
    gondola = equipment["gondola"]
    intermodal = equipment["intermodal"]

    print("Before loading:")
    print(f"  boxcar loaded?      {boxcar.is_loaded}")
    print(f"  tankcar loaded?     {tankcar.is_loaded}")
    print(f"  gondola loaded?     {gondola.is_loaded}")
    print(f"  intermodal loaded?  {intermodal.is_loaded}")
    print()

    boxcar.load_commodity("boxed_produce", food_grade=True)
    tankcar.load_commodity("soy_oil", food_grade=True)
    gondola.load_commodity("scrap_metal")
    intermodal.load_units(2)

    print("After loading:")
    print(f"  boxcar current      {boxcar.current_commodity}")
    print(f"  tankcar current     {tankcar.current_commodity}")
    print(f"  gondola current     {gondola.current_commodity}")
    print(f"  intermodal units    {intermodal.current_units_loaded}")
    print()

    boxcar.unload_commodity()
    tankcar.unload_commodity()
    gondola.unload_commodity()
    intermodal.unload_units(1)

    print("After partial unload / unload:")
    print(f"  boxcar last         {boxcar.last_commodity}")
    print(f"  tankcar last        {tankcar.last_commodity}")
    print(f"  gondola last        {gondola.last_commodity}")
    print(f"  intermodal units    {intermodal.current_units_loaded}")
    print()

    boxcar.clean_boxcar()
    tankcar.clean_tank()
    gondola.clean_gondola()

    print("After cleaning:")
    print(f"  boxcar cleaned      {boxcar.is_cleaned}")
    print(f"  tankcar cleaned     {tankcar.is_cleaned}")
    print(f"  gondola cleaned     {gondola.is_cleaned}")
    print()


if __name__ == "__main__":
    equipment = build_debug_equipment()
    print_equipment_summary(equipment)
    demo_basic_loading(equipment)
